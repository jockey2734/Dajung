"""Format-aware chunking rules (Dajung.md §8.4, system-design §4.1).

포맷별 청킹 규칙 (Dajung.md §8.4, system-design §4.1).
Pure functions — no I/O, no LLM.
순수 함수 — I/O 없음, LLM 없음.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from api.app.core.config import settings
from api.app.ingest.parsers import ParsedDoc

_SLIDE_MARKER = re.compile(r"<!--\s*Slide[^>]*-->", re.IGNORECASE)
_TABLE_LINE = re.compile(r"^\s*\|")


@dataclass
class Chunk:
    text: str
    chunk_index: int
    total_chunks: int  # filled by the pipeline · 파이프라인이 채운다
    locator: str  # "p.3" | "sheet:예산" | "slide:2" | "sec:1" | ""


def chunk_document(doc: ParsedDoc, ext: str) -> list[Chunk]:
    """Split a parsed document into chunks by format rules.

    파싱된 문서를 포맷 규칙대로 청크로 나눈다.
    """
    ext = ext.lower()
    if ext == ".pdf":
        pieces = _chunk_pdf(doc)
    elif ext == ".xlsx":
        pieces = _chunk_xlsx(doc.text)
    elif ext == ".pptx":
        pieces = _chunk_pptx(doc.text)
    elif ext in {".md", ".txt", ".csv"}:
        pieces = _chunk_markdown(doc.text)
    else:  # .docx and anything text-like without headers
        pieces = [("sec", p) for p in _accumulate(_paragraphs(doc.text))]

    merged = _merge_small(pieces)
    return [
        Chunk(text=text, chunk_index=i, total_chunks=0, locator=loc)
        for i, (loc, text) in enumerate(merged)
    ]


# ── format splitters ────────────────────────────────────────────────────────


def _chunk_markdown(text: str) -> list[tuple[str, str]]:
    # First split on h1/h2 headers, then cap each section by size.
    # 먼저 h1/h2 헤더로 나누고, 각 섹션을 크기 제한으로 재분할한다.
    sections: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.startswith(("# ", "## ")) and current:
            sections.append("\n".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append("\n".join(current))

    out: list[tuple[str, str]] = []
    for section in sections:
        if len(section) <= settings.chunk_max_chars:
            out.append(("sec", section))
        else:
            out.extend(("sec", piece) for piece in _accumulate(_paragraphs(section)))
    return out


def _chunk_pdf(doc: ParsedDoc) -> list[tuple[str, str]]:
    if doc.pages is None:
        # docling-fallback pdf has no page map — treat as markdown text.
        # docling 폴백 pdf는 페이지 맵이 없다 — 마크다운 텍스트로 취급.
        return _chunk_markdown(doc.text)

    out: list[tuple[str, str]] = []
    for page_no, page in enumerate(doc.pages, start=1):
        loc = f"p.{page_no}"
        if len(page) <= settings.chunk_max_chars:
            out.append((loc, page))
            continue
        pieces = _accumulate(_paragraphs(page))
        # Overlap: prepend the tail of the previous piece to the next one.
        # 오버랩: 앞 조각 꼬리를 다음 조각 앞에 붙인다.
        overlapped: list[str] = []
        for i, piece in enumerate(pieces):
            if i > 0:
                tail = pieces[i - 1][-settings.chunk_overlap_chars :]
                piece = tail + "\n" + piece
            overlapped.append(piece)
        out.extend((loc, piece) for piece in overlapped)
    return out


def _chunk_pptx(text: str) -> list[tuple[str, str]]:
    if _SLIDE_MARKER.search(text):
        slides = [s for s in _SLIDE_MARKER.split(text) if s.strip()]
        out: list[tuple[str, str]] = []
        for n, slide in enumerate(slides, start=1):
            loc = f"slide:{n}"
            if len(slide) <= settings.chunk_max_chars:
                out.append((loc, slide))
            else:
                out.extend((loc, p) for p in _accumulate(_paragraphs(slide)))
        return out
    return [("slide", p) for p in _accumulate(_paragraphs(text))]


def _chunk_xlsx(text: str) -> list[tuple[str, str]]:
    # MarkItDown emits one "## SheetName" block per sheet with a markdown table.
    # MarkItDown은 시트마다 "## 시트명" 블록 + 마크다운 표를 만든다.
    out: list[tuple[str, str]] = []
    for sheet in _split_sheets(text):
        name, body = sheet
        loc = f"sheet:{name}" if name else "sheet"
        lines = body.splitlines()
        table = [ln for ln in lines if _TABLE_LINE.match(ln)]
        if len(table) <= settings.xlsx_row_block + 2:
            out.append((loc, body))
            continue
        # Long sheet: split data rows into blocks, repeating the header rows.
        # 긴 시트: 데이터 행을 블록으로 나누고 헤더 행을 반복 부착한다.
        header, rows = table[:2], table[2:]
        for start in range(0, len(rows), settings.xlsx_row_block):
            block = rows[start : start + settings.xlsx_row_block]
            out.append((loc, "\n".join(header + block)))
    return out


def _split_sheets(text: str) -> list[tuple[str, str]]:
    sheets: list[tuple[str, str]] = []
    name = ""
    buf: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if buf and "".join(buf).strip():
                sheets.append((name, "\n".join(buf)))
            name = line[3:].strip()
            buf = [line]
        else:
            buf.append(line)
    if buf and "".join(buf).strip():
        sheets.append((name, "\n".join(buf)))
    return sheets


# ── shared helpers ──────────────────────────────────────────────────────────


def _paragraphs(text: str) -> list[str]:
    return [p for p in re.split(r"\n\s*\n", text) if p.strip()]


def _accumulate(paragraphs: list[str]) -> list[str]:
    """Greedily pack paragraphs up to chunk_max_chars.

    문단을 chunk_max_chars까지 탐욕적으로 눌러 담는다.
    """
    pieces: list[str] = []
    buf = ""
    for para in paragraphs:
        if buf and len(buf) + len(para) + 2 > settings.chunk_max_chars:
            pieces.append(buf)
            buf = para
        else:
            buf = f"{buf}\n\n{para}" if buf else para
        # A single paragraph longer than max gets hard-cut.
        # max보다 긴 단일 문단은 강제 절단한다.
        while len(buf) > settings.chunk_max_chars:
            pieces.append(buf[: settings.chunk_max_chars])
            buf = buf[settings.chunk_max_chars :]
    if buf.strip():
        pieces.append(buf)
    return pieces


def _merge_small(pieces: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Merge under-min chunks into the previous one; drop a lone tiny head.

    최소 크기 미만 청크는 앞 청크에 병합, 맨 앞의 외톨이는 버린다.
    """
    merged: list[tuple[str, str]] = []
    for loc, text in pieces:
        if len(text.strip()) < settings.chunk_min_chars:
            if merged:
                prev_loc, prev_text = merged[-1]
                merged[-1] = (prev_loc, prev_text + "\n\n" + text)
            # else: drop — nothing to merge into · 병합 대상 없음, 버림
            continue
        merged.append((loc, text))
    if not merged and pieces:
        # Whole document smaller than min — keep it as one chunk anyway.
        # 문서 전체가 최소 크기 미만 — 그래도 한 청크로 남긴다.
        loc = pieces[0][0]
        merged = [(loc, "\n\n".join(t for _, t in pieces))]
    return merged
