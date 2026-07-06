"""Parser dispatch cases (Dajung.md §9).

파서 디스패치 케이스 (Dajung.md §9).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from api.app.ingest.parsers import (
    ParserEmptyError,
    UnsupportedFormatError,
    parse_file,
)


def test_markdown_parses(tmp_docs: Path) -> None:
    doc = parse_file(tmp_docs / "guide.md")
    assert doc.kind == "text"
    assert "개완" in doc.text
    assert doc.pages is None


def test_txt_parses(tmp_docs: Path) -> None:
    doc = parse_file(tmp_docs / "note.txt")
    assert doc.kind == "text"
    assert "밀폐용기" in doc.text


def test_unsupported_extension_raises(tmp_path: Path) -> None:
    target = tmp_path / "slide.hwp"
    target.write_bytes(b"dummy")
    with pytest.raises(UnsupportedFormatError):
        parse_file(target)


def test_empty_text_file_raises(tmp_path: Path) -> None:
    target = tmp_path / "empty.txt"
    target.write_text("   \n", encoding="utf-8")
    with pytest.raises(ParserEmptyError):
        parse_file(target)


def test_pdf_pages_extracted(tmp_path: Path) -> None:
    # Build a real 2-page pdf with pymupdf — no external service needed.
    # pymupdf로 실제 2페이지 pdf를 만든다 — 외부 서비스 불필요.
    import fitz

    target = tmp_path / "two_pages.pdf"
    # ASCII text — the default pdf base font cannot render Hangul.
    # ASCII 텍스트 — pdf 기본 폰트는 한글을 렌더링하지 못한다.
    with fitz.open() as doc:
        for text in ("first page content. " * 10, "second page content. " * 10):
            page = doc.new_page()
            page.insert_text((72, 72), text)
        doc.save(str(target))

    parsed = parse_file(target)
    assert parsed.kind == "pdf"
    assert parsed.pages is not None and len(parsed.pages) == 2
    assert "first page" in parsed.pages[0]
