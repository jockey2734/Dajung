"""Dajung Ark CLI — MVP1 entry point (Dajung.md §8.2).

Dajung Ark CLI — MVP1 진입점 (Dajung.md §8.2).
Commands: ingest / ask / stats / invite / owner / president. Heavy modules are imported
lazily so the CLI stays responsive and later branches can fill in the implementations.
명령: ingest / ask / stats / invite / owner / president. 무거운 모듈은 지연 임포트한다 —
CLI 반응성을 지키고, 이후 브랜치가 구현을 채워 넣을 수 있게 한다.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api.app.core.config import settings
from api.app.core.logging import configure_logging
from api.app.db.models import User
from api.app.invitations import (
    CreatedInvitation,
    InvitationPrefixAmbiguousError,
    InvitationPrefixNotFoundError,
    InvitationSummary,
    create_invitation,
    list_invitations,
    revoke_invitation,
)
from api.app.owners import (
    OwnerAlreadyExistsError,
    OwnerUserNotFoundError,
    claim_initial_owner,
)
from api.app.presidents import (
    PresidentTransferSummary,
    PresidentTransferValidationError,
    get_current_president,
    list_president_transfers,
    transfer_president,
)

app = typer.Typer(name="dajung", no_args_is_help=True, add_completion=False)
invite_app = typer.Typer(no_args_is_help=True, add_completion=False)
owner_app = typer.Typer(no_args_is_help=True, add_completion=False)
president_app = typer.Typer(no_args_is_help=True, add_completion=False)
app.add_typer(invite_app, name="invite", help="통과번호 관리")
app.add_typer(owner_app, name="owner", help="최초 owner 설정")
app.add_typer(president_app, name="president", help="회장 권한 관리")

# Default CLI identity until serving-phase auth exists (Dajung.md §8.8).
# 서빙 단계 인증이 생기기 전까지의 CLI 기본 신원 (Dajung.md §8.8).
CLI_USER = {"id": "cli-local", "email": "local", "role": "owner"}

_NOT_IMPLEMENTED = "아직 구현되지 않았습니다 — 해당 브랜치({branch}) 머지 후 사용 가능합니다."


@app.callback()
def _init() -> None:
    configure_logging()


def _session_factory() -> async_sessionmaker[AsyncSession]:
    from api.app.db.base import SessionLocal

    return SessionLocal


async def _create_code(note: str | None, days: int) -> CreatedInvitation:
    factory = _session_factory()
    async with factory() as session:
        return await create_invitation(session, note=note, days=days)


async def _list_codes() -> list[InvitationSummary]:
    factory = _session_factory()
    async with factory() as session:
        return await list_invitations(session)


async def _revoke_code(prefix: str) -> InvitationSummary:
    factory = _session_factory()
    async with factory() as session:
        return await revoke_invitation(session, prefix)


async def _claim_owner(email: str) -> User:
    factory = _session_factory()
    async with factory() as session:
        return await claim_initial_owner(session, email)


class PresidentCliError(Exception):
    """Expected president-command failure rendered without a traceback.

    트레이스백 없이 표시할 회장 관리 명령의 예상 오류.
    """


async def _cli_owner(session: AsyncSession) -> User:
    owners = (await session.execute(select(User).where(User.role == "owner"))).scalars().all()
    if len(owners) != 1:
        raise PresidentCliError("owner 계정이 정확히 하나여야 합니다.")
    return owners[0]


async def _set_president(email: str, note: str | None) -> User:
    factory = _session_factory()
    async with factory() as session:
        owner = await _cli_owner(session)
        target = (
            await session.execute(select(User).where(User.email == email.strip().lower()))
        ).scalar_one_or_none()
        if target is None:
            raise PresidentCliError(f"사용자를 찾을 수 없습니다: {email}")
        try:
            return await transfer_president(session, actor=owner, to_user_id=target.id, note=note)
        except PresidentTransferValidationError as exc:
            raise PresidentCliError(str(exc)) from exc


async def _show_president() -> User | None:
    factory = _session_factory()
    async with factory() as session:
        await _cli_owner(session)
        return await get_current_president(session)


async def _president_history() -> list[PresidentTransferSummary]:
    factory = _session_factory()
    async with factory() as session:
        await _cli_owner(session)
        return await list_president_transfers(session)


@invite_app.command("create")
def invite_create(
    note: Annotated[str | None, typer.Option("--note", help="수신자 메모")] = None,
    days: Annotated[int, typer.Option("--days", help="유효 기간(일)")] = 7,
) -> None:
    """Issue a code and show its plaintext exactly once.

    통과번호를 발급하고 평문을 정확히 한 번 표시한다.
    """
    created = asyncio.run(_create_code(note, days))
    typer.echo(f"통과번호: {created.code}")
    typer.echo(f"만료: {created.expires_at.isoformat()}")
    typer.echo(f"메모: {created.note or '-'}")
    typer.echo("주의: 카카오톡·문자로만 전달하고 로그·파일에 기록하지 마세요.")


@invite_app.command("list")
def invite_list() -> None:
    """List safe invitation metadata without plaintext codes.

    평문 없이 안전한 통과번호 메타데이터를 조회한다.
    """
    rows = asyncio.run(_list_codes())
    typer.echo("평문 복원 불가 — SHA-256 해시만 저장됩니다.")
    typer.echo("ID       메모                 만료                       상태    사용 시각")
    if not rows:
        typer.echo("(없음)")
        return
    for row in rows:
        note = (row.note or "-")[:20]
        used_at = row.used_at.isoformat() if row.used_at is not None else "-"
        typer.echo(
            f"{str(row.id)[:8]} {note:<20} "
            f"{row.expires_at.isoformat():<26} {row.status:<5} {used_at}"
        )


@invite_app.command("revoke")
def invite_revoke(
    id_prefix: Annotated[str, typer.Argument(help="통과번호 ID 앞자리")],
) -> None:
    """Expire one invitation selected by an unambiguous ID prefix.

    모호하지 않은 ID prefix로 통과번호 하나를 즉시 만료한다.
    """
    try:
        revoked = asyncio.run(_revoke_code(id_prefix))
    except InvitationPrefixNotFoundError:
        typer.echo(f"일치하는 통과번호가 없습니다: {id_prefix}", err=True)
        raise typer.Exit(code=1) from None
    except InvitationPrefixAmbiguousError:
        typer.echo(f"ID prefix가 모호합니다: {id_prefix}", err=True)
        raise typer.Exit(code=1) from None
    typer.echo(f"폐기 완료: {str(revoked.id)[:8]}")


@owner_app.command("claim")
def owner_claim(
    email: Annotated[str, typer.Argument(help="가입한 최초 owner 이메일")],
) -> None:
    """Promote the first signed-up account to owner exactly once.

    최초 가입 계정을 정확히 한 번 owner로 승격한다.
    """
    try:
        owner = asyncio.run(_claim_owner(email))
    except OwnerAlreadyExistsError:
        typer.echo("이미 owner 계정이 존재합니다.", err=True)
        raise typer.Exit(code=1) from None
    except OwnerUserNotFoundError:
        typer.echo(f"사용자를 찾을 수 없습니다: {email}", err=True)
        raise typer.Exit(code=1) from None
    typer.echo(f"owner 승격 완료: {owner.name} <{owner.email}>")


@president_app.command("set")
def president_set(
    email: Annotated[str, typer.Argument(help="후임자 이메일")],
    note: Annotated[str | None, typer.Option("--note", help="인계 메모")] = None,
) -> None:
    """Appoint an active staff account as president.

    활성 운영진 계정을 회장으로 임명한다.
    """
    try:
        president = asyncio.run(_set_president(email, note))
    except PresidentCliError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from None
    typer.echo(f"회장 임명 완료: {president.name} <{president.email}>")


@president_app.command("show")
def president_show() -> None:
    """Show the current president.

    현재 회장을 표시한다.
    """
    try:
        president = asyncio.run(_show_president())
    except PresidentCliError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from None
    if president is None:
        typer.echo("현재 회장: (없음)")
        return
    typer.echo(f"현재 회장: {president.name} <{president.email}>")


@president_app.command("history")
def president_history() -> None:
    """Show permanent president transfer history newest first.

    영구 회장 인계 기록을 최신순으로 표시한다.
    """
    try:
        rows = asyncio.run(_president_history())
    except PresidentCliError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from None
    if not rows:
        typer.echo("회장 인계 기록: (없음)")
        return
    for row in rows:
        previous = row.from_user.name if row.from_user is not None else "(없음)"
        typer.echo(
            f"{row.transfer.created_at.isoformat()} | {previous} -> {row.to_user.name} | "
            f"처리: {row.actor.name} | 메모: {row.transfer.note or '-'}"
        )


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
    from api.app.rag.answer import run_ask_graph

    try:
        typer.echo(
            run_ask_graph(question, user=CLI_USER, route=route, json_out=json_out, top_k=top_k)
        )
    except Exception as exc:
        # Unreachable Qdrant/API must fail cleanly, never with a traceback.
        # Qdrant·API에 못 닿으면 트레이스백 없이 깨끗하게 실패한다.
        typer.echo(
            f"실행 실패: {type(exc).__name__} — "
            f"Qdrant({settings.qdrant_url})·API 연결을 확인하세요."
        )
        raise typer.Exit(code=1) from exc


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
