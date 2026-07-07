"""Pipeline dry-run behavior — fully offline (Dajung.md §9).

파이프라인 dry-run 동작 — 완전 오프라인 (Dajung.md §9).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from api.app.ingest.pipeline import run_ingest


@pytest.fixture(autouse=True)
def _isolate_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Point manifest/CSV at the temp dir so real project files are untouched.
    # 매니페스트·CSV를 임시 경로로 돌려 실제 프로젝트 파일을 건드리지 않는다.
    monkeypatch.setenv("DAJUNG_MANIFEST_PATH", str(tmp_path / "manifest.json"))
    monkeypatch.setenv("DAJUNG_CSV_PATH", str(tmp_path / "no_such.csv"))
    from api.app.core import config

    monkeypatch.setattr(config, "settings", config.Settings(_env_file=None))  # type: ignore[call-arg]
    # Modules imported `settings` by value — patch their references too.
    # 모듈들이 settings를 값으로 임포트했으므로 참조도 함께 패치한다.
    from api.app.ingest import chunker, pipeline

    monkeypatch.setattr(pipeline, "settings", config.settings)
    monkeypatch.setattr(chunker, "settings", config.settings)


def test_dry_run_counts_and_no_manifest(tmp_docs: Path, tmp_path: Path) -> None:
    report = run_ingest(tmp_docs, dry_run=True)
    assert report.scanned == 2  # guide.md + note.txt
    assert report.upserted_chunks == 0
    assert report.errors == []
    assert not (tmp_path / "manifest.json").exists()


def test_dry_run_excludes(tmp_docs: Path) -> None:
    (tmp_docs / "~$lock.docx").write_bytes(b"x")
    (tmp_docs / "로고.png").write_bytes(b"x")
    incident = tmp_docs / "사건사고"
    incident.mkdir()
    (incident / "사건.txt").write_text("비밀", encoding="utf-8")

    report = run_ingest(tmp_docs, dry_run=True)
    assert report.excluded["tempfile"] == 1
    assert report.excluded["image"] == 1
    assert report.excluded["incident"] == 1
    assert report.scanned == 2


def test_parse_error_recorded_not_raised(tmp_docs: Path) -> None:
    (tmp_docs / "미지원.hwp").write_bytes(b"x")
    report = run_ingest(tmp_docs, dry_run=True)
    assert len(report.errors) == 1
    assert report.errors[0][0] == "미지원.hwp"
    assert "UnsupportedFormatError" in report.errors[0][1]
    # Other files still processed.
    # 다른 파일은 계속 처리된다.
    assert report.scanned == 3


def test_summary_format(tmp_docs: Path) -> None:
    report = run_ingest(tmp_docs, dry_run=True)
    text = report.summary()
    assert "scanned: 2" in text and "errors: 0" in text
