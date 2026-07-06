"""File parsers — extension dispatch (Dajung.md §8.3).

파일 파서 — 확장자 디스패치 (Dajung.md §8.3).
Office formats go through MarkItDown, PDFs through PyMuPDF with a docling
fallback for scan-suspect files, plain text is read directly.
오피스 포맷은 MarkItDown, PDF는 PyMuPDF(스캔 의심 시 docling 폴백),
일반 텍스트는 직접 읽는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_OFFICE_EXTS = {".docx", ".xlsx", ".pptx"}
_TEXT_EXTS = {".md", ".txt", ".csv"}

# Below this many chars a PDF is treated as a scan and retried with docling.
# 이 글자 수 미만이면 스캔 PDF로 보고 docling으로 재시도한다.
_PDF_MIN_CHARS = 50


class ParserError(Exception):
    """Base error for all parsing failures.

    모든 파싱 실패의 기반 예외.
    """


class UnsupportedFormatError(ParserError):
    """Extension outside the MVP1 support list.

    MVP1 지원 목록 밖의 확장자.
    """


class ParserEmptyError(ParserError):
    """Parsed output was empty — likely a scanned or broken file.

    파싱 결과가 비었다 — 스캔본이거나 깨진 파일일 가능성.
    """


@dataclass
class ParsedDoc:
    source_path: Path
    text: str
    kind: str  # "office" | "pdf" | "text"
    pages: list[str] | None  # pdf only — per-page text · pdf만 페이지별 텍스트


def parse_file(path: Path) -> ParsedDoc:
    """Parse one file into markdown-ish text.

    파일 하나를 마크다운형 텍스트로 파싱한다.
    """
    ext = path.suffix.lower()
    if ext in _OFFICE_EXTS:
        return _parse_office(path)
    if ext == ".pdf":
        return _parse_pdf(path)
    if ext in _TEXT_EXTS:
        return _parse_text(path)
    raise UnsupportedFormatError(f"unsupported extension: {path.name}")


def _parse_office(path: Path) -> ParsedDoc:
    # Heavy import — keep it inside the function.
    # 무거운 임포트 — 함수 안에 둔다.
    from markitdown import MarkItDown

    try:
        result = MarkItDown().convert(str(path))
    except Exception as exc:  # third-party errors become ParserError
        raise ParserError(f"markitdown failed on {path.name}: {exc}") from exc
    text = result.text_content or ""
    if not text.strip():
        raise ParserEmptyError(f"empty office document: {path.name}")
    return ParsedDoc(source_path=path, text=text, kind="office", pages=None)


def _parse_pdf(path: Path) -> ParsedDoc:
    import fitz

    try:
        with fitz.open(path) as doc:
            pages = [page.get_text("text") for page in doc]
    except Exception as exc:
        raise ParserError(f"pymupdf failed on {path.name}: {exc}") from exc

    if sum(len(p.strip()) for p in pages) < _PDF_MIN_CHARS:
        # Scan-suspect: retry with docling before giving up (Dajung.md §8.3).
        # 스캔 의심: 포기 전에 docling으로 재시도한다 (Dajung.md §8.3).
        text = _parse_pdf_docling(path)
        if len(text.strip()) < _PDF_MIN_CHARS:
            raise ParserEmptyError(f"empty pdf (scan?): {path.name}")
        return ParsedDoc(source_path=path, text=text, kind="pdf", pages=None)

    return ParsedDoc(source_path=path, text="\n\n".join(pages), kind="pdf", pages=pages)


def _parse_pdf_docling(path: Path) -> str:
    try:
        from docling.document_converter import DocumentConverter

        result = DocumentConverter().convert(str(path))
        markdown: str = result.document.export_to_markdown()
        return markdown
    except Exception:
        # Fallback of a fallback — report as empty, caller raises.
        # 폴백의 폴백 — 빈 결과로 보고하고 호출자가 예외를 낸다.
        return ""


def _parse_text(path: Path) -> ParsedDoc:
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        raise ParserEmptyError(f"empty text file: {path.name}")
    return ParsedDoc(source_path=path, text=text, kind="text", pages=None)
