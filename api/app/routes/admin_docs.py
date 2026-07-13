"""Knowledge-document administration routes.

지식 문서 관리 라우트.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, Form, UploadFile
from starlette.concurrency import run_in_threadpool

from api.app.core.config import settings
from api.app.core.deps import AdminUser
from api.app.core.errors import ApiError
from api.app.documents import (
    DocumentConflictError,
    DocumentInfrastructureError,
    DocumentNotFoundError,
    DocumentValidationError,
    available_document_folders,
    delete_document,
    ingest_document,
    store_document,
)
from api.app.schemas.admin_docs import DocumentUploadOut

router = APIRouter(prefix="/admin/docs", tags=["admin"])


@router.post("", status_code=202)
async def upload_document(
    background_tasks: BackgroundTasks,
    folder: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
    current: AdminUser,
) -> DocumentUploadOut:
    filename = file.filename or ""
    data = await file.read(settings.upload_max_file_bytes + 1)
    if len(data) > settings.upload_max_file_bytes:
        raise ApiError(400, "validation", "파일 크기는 20MB를 넘을 수 없습니다.")
    try:
        target = await run_in_threadpool(store_document, folder, filename, data)
    except DocumentValidationError as exc:
        raise ApiError(400, "validation", str(exc)) from exc
    except DocumentConflictError as exc:
        raise ApiError(409, "document_conflict", "같은 이름의 문서가 이미 있습니다.") from exc
    background_tasks.add_task(ingest_document, target)
    return DocumentUploadOut(folder=folder, filename=filename)


@router.get("/folders")
async def list_document_folders(current: AdminUser) -> list[str]:
    """List safe upload destinations in stable display order.

    안전한 업로드 대상 폴더를 일정한 표시 순서로 반환한다.
    """
    return sorted(available_document_folders())


@router.delete("/{doc_id}", status_code=204)
async def remove_document(doc_id: uuid.UUID, current: AdminUser) -> None:
    try:
        await run_in_threadpool(delete_document, str(doc_id))
    except DocumentNotFoundError as exc:
        raise ApiError(404, "document_not_found", "문서를 찾을 수 없습니다.") from exc
    except DocumentInfrastructureError as exc:
        raise ApiError(503, "qdrant_down", "검색 시스템에서 문서를 제거할 수 없습니다.") from exc
