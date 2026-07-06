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


def test_unimplemented_commands_fail_cleanly(tmp_path: object) -> None:
    # Until feat/cx-cli-ingest / feat/cx-cli-rag merge, commands must exit 1
    # with a pointer to the blocking branch — not a traceback.
    # feat/cx-cli-ingest / feat/cx-cli-rag 머지 전까지 명령은 트레이스백 없이
    # 어느 브랜치가 선행인지 알려주며 exit 1 해야 한다.
    result = runner.invoke(app, ["ask", "테스트 질문"])
    assert result.exit_code == 1
    assert "feat/cx-cli-rag" in result.output

    result = runner.invoke(app, ["stats"])
    assert result.exit_code == 1
    assert "feat/cx-cli-ingest" in result.output
