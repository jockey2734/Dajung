"""Chunker rule cases (Dajung.md §9).

청커 규칙 케이스 (Dajung.md §9).
"""

from __future__ import annotations

from pathlib import Path

from api.app.core.config import settings
from api.app.ingest.chunker import chunk_document
from api.app.ingest.parsers import ParsedDoc


def _doc(text: str, kind: str = "text", pages: list[str] | None = None) -> ParsedDoc:
    return ParsedDoc(source_path=Path("x"), text=text, kind=kind, pages=pages)


def test_markdown_header_split() -> None:
    body = "긴 본문 문장입니다. " * 30  # ~ over min chars per section
    text = f"# 제목\n\n{body}\n\n## 섹션 A\n\n{body}\n\n## 섹션 B\n\n{body}"
    chunks = chunk_document(_doc(text), ".md")
    assert len(chunks) == 3
    assert chunks[1].text.startswith("## 섹션 A")


def test_oversize_section_is_split() -> None:
    para = "가나다라마바사아자차. " * 20
    text = "# 큰 섹션\n\n" + "\n\n".join([para] * 12)  # far beyond chunk_max_chars
    chunks = chunk_document(_doc(text), ".md")
    assert len(chunks) >= 2
    assert all(
        len(c.text) <= settings.chunk_max_chars + settings.chunk_overlap_chars for c in chunks
    )


def test_small_chunks_merged() -> None:
    body = "본문 문장입니다. " * 40
    text = f"# A\n\n{body}\n\n## 짧음\n\n한 줄."
    chunks = chunk_document(_doc(text), ".md")
    # The tiny section must be merged into the previous chunk.
    # 아주 짧은 섹션은 앞 청크에 병합돼야 한다.
    assert len(chunks) == 1
    assert "한 줄." in chunks[0].text


def test_chunk_index_continuous() -> None:
    body = "문장. " * 100
    text = "\n\n".join(f"## S{i}\n\n{body}" for i in range(4))
    chunks = chunk_document(_doc(text), ".md")
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_pdf_page_locators() -> None:
    pages = ["1쪽 내용입니다. " * 30, "2쪽 내용입니다. " * 30]
    chunks = chunk_document(_doc("\n\n".join(pages), kind="pdf", pages=pages), ".pdf")
    assert chunks[0].locator == "p.1"
    assert chunks[-1].locator == "p.2"


def test_xlsx_header_rows_repeated() -> None:
    header = "| 항목 | 금액 |\n|---|---|"
    rows = "\n".join(f"| 품목{i} | {i}000 |" for i in range(settings.xlsx_row_block * 2 + 5))
    text = f"## 예산\n{header}\n{rows}"
    chunks = chunk_document(_doc(text, kind="office"), ".xlsx")
    assert len(chunks) >= 2
    for c in chunks:
        # Every block must carry the header rows again.
        # 모든 블록이 헤더 행을 다시 갖고 있어야 한다.
        assert c.text.splitlines()[0].startswith("| 항목")
        assert c.locator == "sheet:예산"


def test_pptx_slide_markers() -> None:
    slide = "슬라이드 본문입니다. " * 20
    text = f"<!-- Slide number: 1 -->\n{slide}\n<!-- Slide number: 2 -->\n{slide}"
    chunks = chunk_document(_doc(text, kind="office"), ".pptx")
    assert [c.locator for c in chunks] == ["slide:1", "slide:2"]
