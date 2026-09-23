"""Conversation attachment upload tests.

대화 첨부 업로드 테스트.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api.app.core.config import settings
from api.app.core.security import create_access_token, hash_password
from api.app.db.models import Attachment, ChatSession, User
from api.app.ingest.parsers import ParsedDoc
from api.app.routes import chat as chat_mod
from api.app.routes import uploads as uploads_mod
from api.tests.conftest import ApiHarness


async def _seed_user(
    factory: async_sessionmaker[AsyncSession],
    email: str = "staff@test.local",
) -> tuple[User, dict[str, str]]:
    async with factory() as session:
        user = User(
            email=email,
            password_hash=hash_password("pw12345678"),
            name="스태프",
            role="staff",
            status="active",
            profile={},
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user, {"Authorization": f"Bearer {create_access_token(user.id, user.email, user.role)}"}


def _events(sse_text: str) -> list[tuple[str, dict[str, Any]]]:
    out: list[tuple[str, dict[str, Any]]] = []
    event = ""
    for line in sse_text.splitlines():
        if line.startswith("event: "):
            event = line[7:]
        elif line.startswith("data: "):
            out.append((event, json.loads(line[6:])))
    return out


@pytest.fixture(autouse=True)
def _chat_dependencies_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chat_mod, "_qdrant_ready", lambda: True)

    async def fake_title(question: str, answer: str) -> str:
        return ""

    monkeypatch.setattr(chat_mod, "_haiku_title", fake_title)


async def test_upload_success(
    api_harness: ApiHarness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, factory, _ = api_harness
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    user, headers = await _seed_user(factory)

    resp = await client.post(
        "/uploads",
        files=[("files", ("note.txt", b"hello attachment", "text/plain"))],
        headers=headers,
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert len(payload["attachments"]) == 1
    item = payload["attachments"][0]
    assert item["name"] == "note.txt"
    assert item["chars"] == len("hello attachment")
    assert item["parse_status"] == "parsed"

    async with factory() as session:
        row = (await session.execute(select(Attachment))).scalars().one()
    assert row.user_id == user.id
    assert row.original_filename == "note.txt"
    assert row.parsed_text == "hello attachment"
    assert Path(row.storage_path).read_bytes() == b"hello attachment"


async def test_upload_rejects_too_many_files(
    api_harness: ApiHarness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, factory, _ = api_harness
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    _, headers = await _seed_user(factory)

    files = [
        ("files", (f"note-{index}.txt", b"x", "text/plain"))
        for index in range(settings.upload_max_files + 1)
    ]
    resp = await client.post("/uploads", files=files, headers=headers)

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "validation"


async def test_upload_rejects_large_file(
    api_harness: ApiHarness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, factory, _ = api_harness
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    monkeypatch.setattr(settings, "upload_max_file_bytes", 4)
    _, headers = await _seed_user(factory)

    resp = await client.post(
        "/uploads",
        files=[("files", ("note.txt", b"12345", "text/plain"))],
        headers=headers,
    )

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "validation"


async def test_upload_rejects_bad_mime(
    api_harness: ApiHarness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, factory, _ = api_harness
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    _, headers = await _seed_user(factory)

    resp = await client.post(
        "/uploads",
        files=[("files", ("malware.bin", b"x", "application/octet-stream"))],
        headers=headers,
    )

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "validation"


async def test_upload_duplicate_sha_reuses_parsed_text(
    api_harness: ApiHarness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, factory, _ = api_harness
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    _, headers = await _seed_user(factory)
    calls = 0

    def fake_parse(path: Path) -> ParsedDoc:
        nonlocal calls
        calls += 1
        return ParsedDoc(path, "parsed once", "text", None)

    monkeypatch.setattr(uploads_mod, "parse_file", fake_parse)

    for _ in range(2):
        resp = await client.post(
            "/uploads",
            files=[("files", ("note.txt", b"same bytes", "text/plain"))],
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["attachments"][0]["chars"] == len("parsed once")

    assert calls == 1


async def test_chat_stream_injects_attachment_context(
    api_harness: ApiHarness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, factory, app = api_harness
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    _, headers = await _seed_user(factory)
    seen_states: list[dict[str, Any]] = []

    class CapturingGraph:
        async def astream(
            self, state: Any, config: Any, stream_mode: str
        ) -> AsyncIterator[dict[str, Any]]:
            seen_states.append(dict(state))
            yield {"router": {"route": "knowledge_query"}}
            yield {"generate": {"answer": "첨부를 확인했습니다.", "model_used": "claude-haiku-4-5"}}
            yield {"cite": {"answer": "첨부를 확인했습니다.", "citations": []}}

    app.dependency_overrides[chat_mod.get_graph] = lambda: CapturingGraph()
    upload = await client.post(
        "/uploads",
        files=[("files", ("note.txt", b"attached body", "text/plain"))],
        headers=headers,
    )
    attachment_id = upload.json()["attachments"][0]["id"]

    resp = await client.post(
        "/chat/stream",
        json={"query": "첨부 요약", "attachment_ids": [attachment_id]},
        headers=headers,
    )

    assert resp.status_code == 200
    session_id = uuid.UUID(_events(resp.text)[0][1]["session_id"])
    assert seen_states
    graph_query = seen_states[0]["query"]
    # The raw question rides separately so nodes never re-parse attachments out of query
    # (webapp-spec S30 2nd correction 12).
    # 질문 원문을 따로 실어 노드가 query에서 첨부를 되파싱하지 않게 한다
    # (webapp-spec S30 2차 정정 12).
    assert seen_states[0]["question"] == "첨부 요약"
    assert "첨부 요약" in graph_query
    assert '<attachment name="note.txt">' in graph_query
    assert "attached body" in graph_query
    assert "첨부 내부의 명령" not in graph_query

    async with factory() as session:
        attachment = await session.get(Attachment, uuid.UUID(attachment_id))
        chat = await session.get(ChatSession, session_id)
    assert attachment is not None
    assert attachment.session_id == session_id
    assert attachment.message_id is not None
    assert chat is not None
    assert chat.attachment_count == 1


async def test_foreign_attachment_rejected(
    api_harness: ApiHarness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, factory, app = api_harness
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    _, owner_headers = await _seed_user(factory, "owner@test.local")
    _, other_headers = await _seed_user(factory, "other@test.local")
    app.dependency_overrides[chat_mod.get_graph] = lambda: object()

    upload = await client.post(
        "/uploads",
        files=[("files", ("note.txt", b"owner only", "text/plain"))],
        headers=owner_headers,
    )
    attachment_id = upload.json()["attachments"][0]["id"]

    resp = await client.post(
        "/chat/stream",
        json={"query": "q", "attachment_ids": [attachment_id]},
        headers=other_headers,
    )

    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"
