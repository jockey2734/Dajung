"""Contextual Retrieval headers via Haiku (Dajung.md §8.7).

Haiku로 만드는 Contextual Retrieval 헤더 (Dajung.md §8.7).
API failures degrade to a metadata-only header — ingest never aborts here.
API 실패 시 메타데이터 헤더로 축소 — 여기서 ingest를 중단하지 않는다.
"""

from __future__ import annotations

from api.app.core.config import settings
from api.app.core.logging import get_logger
from api.app.ingest.chunker import Chunk
from api.app.llm.anthropic_client import complete

log = get_logger(__name__)

_DOC_SUMMARY_PROMPT = (
    "다음 문서의 내용을 2문장 이내 한국어로 요약하세요. 요약만 출력하세요.\n\n{body}"
)

_CHUNK_HEADER_PROMPT = (
    "다음은 문서 「{source_file}」({category}, {semester})의 일부입니다.\n"
    "문서 요약: {doc_summary}\n\n"
    "아래 청크가 문서 내에서 어떤 내용을 다루는지 1~2문장, 100자 이내로 "
    "한국어로 요약하세요.\n요약만 출력하세요.\n\n청크:\n{chunk_text}"
)

# Cap the document text sent for the one-shot summary.
# 1회 문서 요약에 보내는 본문 길이 상한.
_DOC_SUMMARY_MAX_CHARS = 6000
_CHUNK_PROMPT_MAX_CHARS = 1500


def summarize_document(text: str) -> str:
    """One Haiku call per document — 2-sentence summary, empty on failure.

    문서당 Haiku 1회 — 2문장 요약, 실패 시 빈 문자열.
    """
    try:
        return complete(
            model=settings.model_haiku,
            system_blocks=[],
            user_text=_DOC_SUMMARY_PROMPT.format(body=text[:_DOC_SUMMARY_MAX_CHARS]),
            max_tokens=settings.max_tokens_header,
        ).strip()
    except Exception as exc:
        log.warning("doc summary failed, using metadata-only headers", error=str(exc))
        return ""


def header_for_chunk(
    chunk: Chunk,
    source_file: str,
    category: str,
    semester: str | None,
    doc_summary: str,
) -> str:
    """Build '[문서: …]\\n[맥락: …]' header; context line dropped on failure.

    '[문서: …]\\n[맥락: …]' 헤더 생성. 실패 시 맥락 줄은 생략한다.
    """
    base = f"[문서: {source_file} | {chunk.locator} | 분류: {category or '미분류'}]"
    if not doc_summary:
        return base
    try:
        context = complete(
            model=settings.model_haiku,
            system_blocks=[],
            user_text=_CHUNK_HEADER_PROMPT.format(
                source_file=source_file,
                category=category or "미분류",
                semester=semester or "학기 미상",
                doc_summary=doc_summary,
                chunk_text=chunk.text[:_CHUNK_PROMPT_MAX_CHARS],
            ),
            max_tokens=settings.max_tokens_header,
        ).strip()
    except Exception as exc:
        log.warning("chunk header failed", locator=chunk.locator, error=str(exc))
        return base
    return f"{base}\n[맥락: {context}]" if context else base
