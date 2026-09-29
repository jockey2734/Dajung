"""CLI skeleton smoke tests.

CLI 골격 스모크 테스트.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from api.app.cli import app

runner = CliRunner()


def test_help_lists_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in ("ingest", "ask", "stats", "invite", "owner", "president"):
        assert command in result.output


def test_ask_without_qdrant_fails_cleanly() -> None:
    # No live Qdrant in unit tests — ask must exit 1 with a clear message
    # and must NOT have loaded the heavy embedder first.
    # 단위 테스트에는 Qdrant가 없다 — ask는 임베더를 올리기 전에
    # 명확한 메시지와 함께 exit 1 해야 한다.
    result = runner.invoke(app, ["ask", "테스트 질문"])
    assert result.exit_code == 1
    assert "Qdrant" in result.output


def test_stats_without_qdrant_fails_cleanly() -> None:
    # No live Qdrant in unit tests — must exit 1 with a clear message.
    # 단위 테스트에는 Qdrant가 없다 — 명확한 메시지와 함께 exit 1.
    result = runner.invoke(app, ["stats"])
    assert result.exit_code == 1
    assert "Qdrant" in result.output


def test_ingest_without_inventory_exits_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A clear one-line refusal and exit code 1, not a traceback.
    # 트레이스백이 아니라 한 줄 중단 메시지와 종료 코드 1.
    from api.app.core import config

    (tmp_path / "note.txt").write_text("합성 본문\n", encoding="utf-8")
    monkeypatch.setattr(config.settings, "csv_path", tmp_path / "missing.csv")
    monkeypatch.setattr(config.settings, "data_dir", tmp_path)

    result = runner.invoke(app, ["ingest", str(tmp_path), "--dry-run"])

    assert result.exit_code == 1
    assert "file inventory missing or empty" in result.output
