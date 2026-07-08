"""Indexed-file listing from Qdrant payloads (serving-plan §1).

Qdrant payload에서 인덱싱 파일 목록 (serving-plan §1).
No separate file registry — the vector store is the source of truth.
별도 파일 대장 없음 — 벡터 스토어가 진실 소스다.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from starlette.concurrency import run_in_threadpool

from api.app.core.config import settings
from api.app.core.deps import CurrentUser
from api.app.core.errors import ApiError
from api.app.schemas.chat import FileEntry, FileListResponse

router = APIRouter(tags=["files"])

_PAGE = 256
_FIELDS = ["doc_id", "source_file", "doc_type", "semester", "restricted", "total_chunks"]


def _scan_files() -> list[dict[str, Any]]:
    """Scroll all chunk payloads and aggregate one entry per document.

    청크 payload를 전부 스크롤해 문서당 한 항목으로 집계한다.
    """
    from api.app.rag.qdrant_store import get_client

    client = get_client()
    if not client.collection_exists(settings.collection):
        return []
    docs: dict[str, dict[str, Any]] = {}
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=settings.collection,
            limit=_PAGE,
            offset=offset,
            with_payload=_FIELDS,
            with_vectors=False,
        )
        for p in points:
            payload = p.payload or {}
            doc_id = str(payload.get("doc_id", ""))
            if not doc_id:
                continue
            entry = docs.setdefault(
                doc_id,
                {
                    "doc_id": doc_id,
                    "source_file": str(payload.get("source_file", "")),
                    "doc_type": str(payload.get("doc_type", "misc")),
                    "semester": payload.get("semester"),
                    "restricted": bool(payload.get("restricted", False)),
                    "chunk_count": 0,
                },
            )
            entry["chunk_count"] += 1
        if offset is None:
            break
    return sorted(docs.values(), key=lambda d: str(d["source_file"]))


@router.get("/files")
async def list_files(current: CurrentUser) -> FileListResponse:
    try:
        # Sync qdrant client — keep the event loop free.
        # 동기 qdrant 클라이언트 — 이벤트 루프를 막지 않는다.
        entries = await run_in_threadpool(_scan_files)
    except Exception as exc:
        raise ApiError(503, "qdrant_down", "검색 시스템에 연결할 수 없습니다.") from exc
    return FileListResponse(files=[FileEntry(**e) for e in entries])
