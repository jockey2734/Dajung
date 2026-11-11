"""Contextual Retrieval headers via Haiku (Dajung.md §8.7).

Haiku로 만드는 Contextual Retrieval 헤더 (Dajung.md §8.7).
The model says what the document is and what role each chunk plays; it does not
restate content. Output passes through the term list (prompts/terms.yaml).
모델은 문서가 무엇인지, 청크가 어떤 역할인지 쓴다 — 내용을 다시 요약하지 않는다.
출력은 용어 사전(prompts/terms.yaml)을 거친다.
API failures degrade to a metadata-only header — ingest never aborts here.
API 실패 시 메타데이터 헤더로 축소 — 여기서 ingest를 중단하지 않는다.
"""

from __future__ import annotations

from api.app.core.config import settings
from api.app.core.logging import get_logger
from api.app.ingest.chunker import Chunk
from api.app.ingest.terms import Terms, get_terms
from api.app.llm.anthropic_client import complete

log = get_logger(__name__)

# Shared rules, tuned on qwen3.5:9b (2026-11-05): no names, keep proper nouns as written.
# 공통 규칙 (qwen3.5:9b로 조정, 2026-11-05): 이름 금지, 고유명사는 원문 표기 그대로.
_RULES = (
    "사람 이름은 쓰지 말고, 필요하면 직책(회장·총무 등)으로 쓰세요.\n"
    "원문에 나오는 행사·프로그램 이름과 영문 약어는 바꾸거나 풀어 쓰지 말고 "
    "원문 표기 그대로 쓰세요.\n"
)

_DOC_SUMMARY_PROMPT = (
    "다음 문서가 어떤 문서인지 설명하세요. 내용 요약이 아닙니다.\n"
    "- 문서 종류 (예: 기획서·회의록·결산·공지·인수인계서·세미나 자료)\n"
    "- 무엇을 위해 만든 문서인지 (목적·쓰임)\n"
    "- 관련 행사·학기·직책 (원문에 있을 때만)\n"
    "2문장 이내 한국어. 세부 수치·목록은 쓰지 말고, 원문에 없는 사실은 쓰지 마세요.\n\n"
    + _RULES
    + "{term_list}\n문서:\n{body}"
)

_CHUNK_HEADER_PROMPT = (
    "다음은 문서 「{source_file}」({category}, {semester})의 일부입니다.\n"
    "문서 설명: {doc_summary}\n\n"
    "아래 청크가 이 문서에서 어떤 부분이며 어떤 역할을 하는지 1문장, {max_chars}자 이내로 "
    "쓰세요.\n"
    '예: "행사 기획서 중 예산 항목의 장소 대여비 산출 근거 부분."\n'
    "청크 내용을 다시 요약하지 마세요. 원문에 없는 사실은 쓰지 마세요.\n\n"
    + _RULES
    + "{term_list}\n청크:\n{chunk_text}"
)

# Cap the document text sent for the one-shot summary.
# 1회 문서 요약에 보내는 본문 길이 상한.
_DOC_SUMMARY_MAX_CHARS = 6000
_CHUNK_PROMPT_MAX_CHARS = 1500


def _term_line(terms: Terms, source: str) -> str:
    # Acronyms and club terms found in the source, named so the model keeps them as is.
    # 원문에서 찾은 약어·동아리 용어 — 이름을 짚어 줘야 모델이 그대로 쓴다.
    found = terms.to_keep(
        source,
        max_acronyms=settings.header_keep_max_acronyms,
        max_terms=settings.header_keep_max_terms,
    )
    return f"원문 표기 그대로 쓸 용어: {', '.join(found)}\n" if found else ""


def summarize_document(text: str) -> str:
    """One Haiku call per document — what the document is, empty on failure.

    문서당 Haiku 1회 — 어떤 문서인지 설명, 실패 시 빈 문자열.
    """
    terms = get_terms()
    body = text[:_DOC_SUMMARY_MAX_CHARS]
    try:
        summary = complete(
            model=settings.model_haiku,
            system_blocks=[],
            user_text=_DOC_SUMMARY_PROMPT.format(term_list=_term_line(terms, body), body=body),
            max_tokens=settings.max_tokens_header,
        ).strip()
    except Exception as exc:
        log.warning("doc summary failed, using metadata-only headers", error=str(exc))
        return ""
    return terms.unify(summary, source=body)


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
    terms = get_terms()
    chunk_text = chunk.text[:_CHUNK_PROMPT_MAX_CHARS]
    # Newlines keep words from different fields from gluing into one acronym.
    # 줄바꿈으로 구분해 서로 다른 필드의 글자가 붙어 약어처럼 보이지 않게 한다.
    source = "\n".join((chunk_text, source_file, category, semester or ""))
    try:
        context = complete(
            model=settings.model_haiku,
            system_blocks=[],
            user_text=_CHUNK_HEADER_PROMPT.format(
                source_file=source_file,
                category=category or "미분류",
                semester=semester or "학기 미상",
                doc_summary=doc_summary,
                max_chars=settings.header_context_max_chars,
                term_list=_term_line(terms, source),
                chunk_text=chunk_text,
            ),
            max_tokens=settings.max_tokens_header,
        ).strip()
    except Exception as exc:
        log.warning("chunk header failed", locator=chunk.locator, error=str(exc))
        return base
    context = terms.unify(context, source=source)[: settings.header_context_max_chars].rstrip()
    return f"{base}\n[맥락: {context}]" if context else base
