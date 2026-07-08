"""Conversation attachment uploads — S2.

대화 첨부 업로드 — S2.
"""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, File, UploadFile
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from api.app.core.config import settings
from api.app.core.deps import CurrentUser, SessionDep
from api.app.core.errors import ApiError
from api.app.db.models import Attachment
from api.app.ingest.parsers import ParserError, parse_file
from api.app.schemas.uploads import AttachmentUploadOut, UploadResponse

router = APIRouter(tags=["uploads"])

_ALLOWED_MIME = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "image/jpeg",
    "image/png",
    "text/markdown",
    "text/plain",
}
_IMAGE_MIME = {"image/jpeg", "image/png"}


def _parse_upload_bytes(
    data: bytes, filename: str, mime_type: str, storage_path: Path
) -> tuple[str, int, Literal["parsed", "failed"], str | None]:
    """Parse uploaded bytes with the existing parser dispatch.

    기존 parser dispatch로 업로드 바이트를 파싱한다.
    """
    if mime_type in _IMAGE_MIME:
        return "", 0, "parsed", None

    suffix = Path(filename).suffix.lower()
    parse_path = storage_path.with_name(f"{storage_path.name}{suffix}")
    parse_path.write_bytes(data)
    try:
        parsed = parse_file(parse_path)
    except ParserError as exc:
        return "", 0, "failed", str(exc)
    finally:
        parse_path.unlink(missing_ok=True)

    return parsed.text, len(parsed.text), "parsed", None


async def _existing_parsed_text(
    session: SessionDep, sha256: str
) -> tuple[str, int, Literal["parsed"], None] | None:
    result = await session.execute(
        select(Attachment)
        .where(Attachment.sha256 == sha256, Attachment.parse_status == "parsed")
        .limit(1)
    )
    attachment = result.scalar_one_or_none()
    if attachment is None:
        return None
    return attachment.parsed_text, attachment.parsed_chars, "parsed", None


@router.post("/uploads")
async def upload_files(
    files: Annotated[list[UploadFile], File()],
    current: CurrentUser,
    session: SessionDep,
) -> UploadResponse:
    if len(files) > settings.upload_max_files:
        raise ApiError(
            400,
            "validation",
            f"파일은 한 번에 최대 {settings.upload_max_files}개까지 첨부할 수 있습니다.",
        )

    buffered: list[tuple[UploadFile, bytes, str, str]] = []
    for file in files:
        filename = file.filename or "upload"
        mime_type = file.content_type or ""
        if mime_type not in _ALLOWED_MIME:
            raise ApiError(400, "validation", "지원하지 않는 파일 형식입니다.")
        data = await file.read()
        if len(data) > settings.upload_max_file_bytes:
            raise ApiError(400, "validation", "파일 크기는 20MB를 넘을 수 없습니다.")
        buffered.append((file, data, filename, mime_type))

    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    response_items: list[AttachmentUploadOut] = []
    parsed_cache: dict[str, tuple[str, int, Literal["parsed", "failed"], str | None]] = {}

    for _file, data, filename, mime_type in buffered:
        attachment_id = uuid.uuid4()
        storage_path = settings.upload_dir / str(attachment_id)
        sha256 = hashlib.sha256(data).hexdigest()
        storage_path.write_bytes(data)

        parsed = parsed_cache.get(sha256)
        if parsed is None:
            existing = await _existing_parsed_text(session, sha256)
            if existing is not None:
                parsed = existing
            else:
                parsed = await run_in_threadpool(
                    _parse_upload_bytes, data, filename, mime_type, storage_path
                )
            parsed_cache[sha256] = parsed

        parsed_text, parsed_chars, parse_status, parse_error = parsed
        attachment = Attachment(
            id=attachment_id,
            user_id=current.id,
            original_filename=filename,
            mime_type=mime_type,
            byte_size=len(data),
            sha256=sha256,
            storage_path=str(storage_path),
            parsed_text=parsed_text,
            parsed_chars=parsed_chars,
            parse_status=parse_status,
            parse_error=parse_error,
        )
        session.add(attachment)
        response_items.append(
            AttachmentUploadOut(
                id=attachment_id,
                name=filename,
                chars=parsed_chars,
                parse_status=parse_status,
            )
        )

    await session.commit()
    return UploadResponse(attachments=response_items)
