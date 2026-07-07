"""Dajung Ark CLI — MVP1 entry point (Dajung.md §8.2).

Dajung Ark CLI — MVP1 진입점 (Dajung.md §8.2).
Commands: ingest / ask / stats. Heavy modules are imported lazily so the
CLI stays responsive and later branches can fill in the implementations.
명령: ingest / ask / stats. 무거운 모듈은 지연 임포트한다 — CLI 반응성을
지키고, 이후 브랜치가 구현을 채워 넣을 수 있게 한다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from api.app.core.config import settings
from api.app.core.logging import configure_logging

app = typer.Typer(name="dajung", no_args_is_help=True, add_completion=False)

# Default CLI identity until serving-phase auth exists (Dajung.md §8.8).
# 서빙 단계 인증이 생기기 전까지의 CLI 기본 신원 (Dajung.md §8.8).
CLI_USER = {"id": "cli-local", "email": "local", "role": "owner"}

_NOT_IMPLEMENTED = "아직 구현되지 않았습니다 — 해당 브랜치({branch}) 머지 후 사용 가능합니다."


@app.callback()
def _init() -> None:
    configure_logging()


@app.command()
def ingest(
    target_dir: Annotated[Path, typer.Argument(help="인덱싱할 디렉토리")],
    rebuild: Annotated[
        bool, typer.Option("--rebuild", help="매니페스트 무시하고 전체 재인덱싱")
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="파싱·청킹 통계만, 업서트 없음")
    ] = False,
) -> None:
    """Index local files into Qdrant.

    로컬 파일을 Qdrant에 인덱싱한다.
    """
    try:
        from api.app.ingest.pipeline import run_ingest
    except ImportError as exc:
        typer.echo(_NOT_IMPLEMENTED.format(branch="feat/cx-cli-ingest"))
        raise typer.Exit(code=1) from exc
    report = run_ingest(target_dir, rebuild=rebuild, dry_run=dry_run)
    typer.echo(report.summary())


@app.command()
def ask(
    question: Annotated[str, typer.Argument(help="질문")],
    route: Annotated[str, typer.Option("--route", help="auto|knowledge|handover")] = "auto",
    json_out: Annotated[bool, typer.Option("--json", help="JSON으로 출력")] = False,
    top_k: Annotated[int, typer.Option("--top-k", help="리랭크 상위 K")] = 0,
) -> None:
    """Ask a question against the indexed club knowledge.

    인덱싱된 동아리 지식에 질문한다.
    """
    try:
        from api.app.rag.answer import run_ask
    except ImportError as exc:
        typer.echo(_NOT_IMPLEMENTED.format(branch="feat/cx-cli-rag"))
        raise typer.Exit(code=1) from exc
    typer.echo(run_ask(question, user=CLI_USER, route=route, json_out=json_out, top_k=top_k))


@app.command()
def stats() -> None:
    """Show Qdrant collection statistics.

    Qdrant 컬렉션 통계를 출력한다.
    """
    from api.app.rag.qdrant_store import collection_stats

    try:
        typer.echo(collection_stats())
    except Exception as exc:
        # Fail loudly but cleanly when Qdrant is unreachable (no traceback).
        # Qdrant에 못 닿으면 트레이스백 없이 명확하게 실패한다.
        typer.echo(f"Qdrant 연결 실패 ({settings.qdrant_url}): {type(exc).__name__}")
        raise typer.Exit(code=1) from exc


if __name__ == "__main__":
    app()
