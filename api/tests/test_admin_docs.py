"""Knowledge-document administration integration tests.

지식 문서 관리 통합 테스트.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api.app import documents
from api.app.core.config import settings
from api.app.core.security import create_access_token, hash_password
from api.app.db.models import User
from api.app.ingest.metadata import doc_id_for
from api.app.ingest.pipeline import IngestReport
from api.app.routes import files as files_routes
from api.tests.conftest import ApiHarness


async def _owner_headers(factory: async_sessionmaker[AsyncSession]) -> dict[str, str]:
    user = User(
        email="owner@example.com",
        password_hash=hash_password("docs-password"),  # pragma: allowlist secret
        name="관리자",
        role="owner",
        status="active",
        profile={},
    )
    async with factory() as session:
        session.add(user)
        await session.commit()
    token = create_access_token(user.id, user.email, user.role)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def document_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    data_dir = tmp_path / "data"
    knowledge = data_dir / "knowledge"
    knowledge.mkdir(parents=True)
    (data_dir / "사건사고").mkdir()
    manifest = data_dir / ".ingest_manifest.json"
    monkeypatch.setattr(settings, "data_dir", data_dir)
    monkeypatch.setattr(settings, "manifest_path", manifest)
    monkeypatch.setattr(settings, "upload_max_file_bytes", 32)
    return data_dir, manifest


@pytest.mark.parametrize(
    ("folder", "filename"),
    [
        ("knowledge", "../evil.md"),
        ("knowledge", "..\\evil.md"),
        ("knowledge", ".hidden.md"),
        ("knowledge", "unsupported.exe"),
        ("사건사고", "incident.md"),
        ("missing", "note.md"),
    ],
)
async def test_upload_rejects_unsafe_targets(
    api_harness: ApiHarness,
    document_paths: tuple[Path, Path],
    folder: str,
    filename: str,
) -> None:
    client, factory, _ = api_harness
    headers = await _owner_headers(factory)

    response = await client.post(
        "/admin/docs",
        headers=headers,
        data={"folder": folder},
        files={"file": (filename, b"synthetic", "text/markdown")},
    )

    assert response.status_code == 400
    assert not any(
        path.is_file() for path in document_paths[0].rglob("*") if ".trash" not in path.parts
    )


async def test_upload_rejects_oversize_and_existing_file(
    api_harness: ApiHarness,
    document_paths: tuple[Path, Path],
) -> None:
    client, factory, _ = api_harness
    headers = await _owner_headers(factory)
    knowledge = document_paths[0] / "knowledge"
    (knowledge / "exists.md").write_text("original", encoding="utf-8")

    oversize = await client.post(
        "/admin/docs",
        headers=headers,
        data={"folder": "knowledge"},
        files={"file": ("large.md", b"x" * 33, "text/markdown")},
    )
    conflict = await client.post(
        "/admin/docs",
        headers=headers,
        data={"folder": "knowledge"},
        files={"file": ("exists.md", b"replacement", "text/markdown")},
    )

    assert oversize.status_code == 400
    assert conflict.status_code == 409
    assert (knowledge / "exists.md").read_text(encoding="utf-8") == "original"


async def test_upload_rejects_symlinked_folder(
    api_harness: ApiHarness,
    document_paths: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    client, factory, _ = api_harness
    headers = await _owner_headers(factory)
    outside = tmp_path / "outside"
    outside.mkdir()
    (document_paths[0] / "linked").symlink_to(outside, target_is_directory=True)

    response = await client.post(
        "/admin/docs",
        headers=headers,
        data={"folder": "linked"},
        files={"file": ("escape.md", b"synthetic", "text/markdown")},
    )

    assert response.status_code == 400
    assert not (outside / "escape.md").exists()


async def test_upload_stores_and_dispatches_one_file(
    api_harness: ApiHarness,
    document_paths: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, factory, _ = api_harness
    headers = await _owner_headers(factory)
    ingested: list[Path] = []

    def fake_ingest(path: Path) -> IngestReport:
        ingested.append(path)
        return IngestReport(scanned=1, upserted_chunks=1)

    monkeypatch.setattr(documents, "run_ingest_file", fake_ingest)
    response = await client.post(
        "/admin/docs",
        headers=headers,
        data={"folder": "knowledge"},
        files={"file": ("guide.md", b"# synthetic guide", "text/markdown")},
    )

    target = document_paths[0] / "knowledge" / "guide.md"
    assert response.status_code == 202
    assert response.json() == {
        "folder": "knowledge",
        "filename": "guide.md",
        "status": "processing",
    }
    assert target.read_bytes() == b"# synthetic guide"
    assert ingested == [target]


async def test_delete_moves_to_trash_removes_manifest_and_files_listing(
    api_harness: ApiHarness,
    document_paths: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, factory, _ = api_harness
    headers = await _owner_headers(factory)
    data_dir, manifest_path = document_paths
    source = data_dir / "knowledge" / "delete-me.md"
    source.write_text("synthetic", encoding="utf-8")
    manifest_path.write_text(json.dumps({str(source): "hash"}), encoding="utf-8")
    doc_id = doc_id_for(str(source))
    visible = {doc_id}

    def fake_delete(deleted_id: str) -> None:
        visible.discard(deleted_id)

    def fake_scan() -> list[dict[str, object]]:
        if doc_id not in visible:
            return []
        return [
            {
                "doc_id": doc_id,
                "source_file": source.name,
                "doc_type": "misc",
                "semester": None,
                "restricted": False,
                "chunk_count": 1,
            }
        ]

    monkeypatch.setattr(documents, "delete_doc", fake_delete)
    monkeypatch.setattr(files_routes, "_scan_files", fake_scan)
    assert len((await client.get("/files", headers=headers)).json()["files"]) == 1

    deleted = await client.delete(f"/admin/docs/{doc_id}", headers=headers)

    assert deleted.status_code == 204
    assert not source.exists()
    trash_files = list((data_dir / ".trash").iterdir())
    assert len(trash_files) == 1
    assert trash_files[0].read_text(encoding="utf-8") == "synthetic"
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == {}
    assert (await client.get("/files", headers=headers)).json()["files"] == []


async def test_delete_restores_file_and_manifest_when_qdrant_fails(
    api_harness: ApiHarness,
    document_paths: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, factory, _ = api_harness
    headers = await _owner_headers(factory)
    data_dir, manifest_path = document_paths
    source = data_dir / "knowledge" / "restore.md"
    source.write_text("synthetic", encoding="utf-8")
    manifest = {str(source): "hash"}
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    def fail_delete(doc_id: str) -> None:
        raise ConnectionError("synthetic qdrant failure")

    monkeypatch.setattr(documents, "delete_doc", fail_delete)
    response = await client.delete(f"/admin/docs/{doc_id_for(str(source))}", headers=headers)

    assert response.status_code == 503
    assert source.read_text(encoding="utf-8") == "synthetic"
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == manifest
    assert list((data_dir / ".trash").iterdir()) == []


async def test_document_routes_require_admin(
    api_harness: ApiHarness,
    document_paths: tuple[Path, Path],
) -> None:
    client, factory, _ = api_harness
    staff = User(
        email="staff@example.com",
        password_hash=hash_password("docs-password"),  # pragma: allowlist secret
        name="운영진",
        role="staff",
        status="active",
        expires_at=datetime.now(UTC) + timedelta(days=30),
        profile={},
    )
    async with factory() as session:
        session.add(staff)
        await session.commit()
    headers = {"Authorization": f"Bearer {create_access_token(staff.id, staff.email, staff.role)}"}

    response = await client.post(
        "/admin/docs",
        headers=headers,
        data={"folder": "knowledge"},
        files={"file": ("guide.md", b"text", "text/markdown")},
    )

    assert response.status_code == 403
