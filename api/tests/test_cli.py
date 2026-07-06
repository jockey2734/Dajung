"""CLI skeleton smoke tests.

CLI 골격 스모크 테스트.
"""

from __future__ import annotations

from typer.testing import CliRunner

from api.app.cli import app

runner = CliRunner()


def test_help_lists_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in ("ingest", "ask", "stats"):
        assert command in result.output


def test_unimplemented_ask_fails_cleanly() -> None:
    # Until feat/cx-cli-rag merges, ask must exit 1 with a pointer to the
    # blocking branch — not a traceback.
    # feat/cx-cli-rag 머지 전까지 ask는 트레이스백 없이 선행 브랜치를
    # 알려주며 exit 1 해야 한다.
    result = runner.invoke(app, ["ask", "테스트 질문"])
    assert result.exit_code == 1
    assert "feat/cx-cli-rag" in result.output


def test_stats_without_qdrant_fails_cleanly() -> None:
    # No live Qdrant in unit tests — must exit 1 with a clear message.
    # 단위 테스트에는 Qdrant가 없다 — 명확한 메시지와 함께 exit 1.
    result = runner.invoke(app, ["stats"])
    assert result.exit_code == 1
    assert "Qdrant" in result.output
