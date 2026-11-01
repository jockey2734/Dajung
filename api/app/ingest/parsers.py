"""File parsers — extension dispatch (Dajung.md §8.3, ADR-030).

파일 파서 — 확장자 디스패치 (Dajung.md §8.3, ADR-030).
Office formats go through MarkItDown; PDFs through opendataloader-pdf local mode merged
page-by-page with PyMuPDF (docling for scan-suspect files); plain text is read directly.
오피스 포맷은 MarkItDown, PDF는 opendataloader-pdf 로컬 모드를 PyMuPDF와 페이지 단위로
병합(스캔 의심 시 docling), 일반 텍스트는 직접 읽는다.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from api.app.core.config import settings
from api.app.core.logging import get_logger

log = get_logger(__name__)

_OFFICE_EXTS = {".docx", ".xlsx", ".pptx"}
_TEXT_EXTS = {".md", ".txt", ".csv"}

# Below this many chars a PDF is treated as a scan and retried with docling.
# 이 글자 수 미만이면 스캔 PDF로 보고 docling으로 재시도한다.
_PDF_MIN_CHARS = 50

# Page marker handed to opendataloader-pdf; it is written before every page,
# page 1 included, so splitting on it recovers the exact page list (ADR-030).
# opendataloader-pdf에 넘기는 페이지 표식. 1페이지를 포함해 모든 페이지 앞에
# 쓰이므로 이것으로 쪼개면 정확한 페이지 목록이 된다 (ADR-030).
_ODL_PAGE_SEPARATOR = "<!-- dajung-page %page-number% -->"
_ODL_PAGE_RE = re.compile(r"^<!-- dajung-page \d+ -->$", re.MULTILINE)
# Words for the per-page coverage check: Hangul/Latin/digit runs of 2+ chars.
# 페이지 커버리지 비교용 단어: 한글·라틴·숫자 2자 이상 연속.
_WORD_RE = re.compile(r"[가-힣A-Za-z0-9]{2,}")
# Markdown structure ODL wraps around text: table separator rows, table rows (a line
# that starts and ends with a pipe), heading markers and <br>. The scan check strips it
# so an empty table grid from a scanned page still reads as text-less (2 real scans,
# 2026-11-01). Patterns stay within one line so plain text is never touched.
# ODL이 본문에 두르는 마크다운 구조: 표 구분 행, 표 행(`|`로 시작하고 끝나는 줄),
# 제목 표식, <br>. 스캔 판정에서 걷어내, 스캔 페이지의 빈 표 격자가 본문 없음으로
# 읽히게 한다 (실제 스캔 2건, 2026-11-01). 패턴은 한 줄 안에서만 맞아 평문은 건드리지 않는다.
_MD_TABLE_SEP_RE = re.compile(
    r"^[ \t]*\|?[ \t]*:?-{3,}:?[ \t]*(\|[ \t]*:?-{3,}:?[ \t]*)*\|?[ \t]*$", re.MULTILINE
)
_MD_TABLE_ROW_RE = re.compile(r"^[ \t]*\|.*\|[ \t]*$", re.MULTILINE)
_MD_HEADING_RE = re.compile(r"^#{1,6}[ \t]+", re.MULTILINE)


def _split_odl_pages(markdown: str) -> list[str]:
    """Split ODL markdown on the page markers; no marker means one page.

    ODL 마크다운을 페이지 표식으로 나눈다. 표식이 없으면 한 페이지다.
    """
    parts = _ODL_PAGE_RE.split(markdown)
    if len(parts) == 1:
        return [markdown.strip()]
    return [part.strip() for part in parts[1:]]


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
    pages = _pdf_pages(path)
    if sum(_text_chars(p) for p in pages) < _PDF_MIN_CHARS:
        # Scan-suspect: retry with docling before giving up (Dajung.md §8.3).
        # 스캔 의심: 포기 전에 docling으로 재시도한다 (Dajung.md §8.3).
        text = _parse_pdf_docling(path)
        if len(text.strip()) < _PDF_MIN_CHARS:
            raise ParserEmptyError(f"empty pdf (scan?): {path.name}")
        return ParsedDoc(source_path=path, text=text, kind="pdf", pages=None)

    return ParsedDoc(source_path=path, text="\n\n".join(pages), kind="pdf", pages=pages)


def _text_chars(page: str) -> int:
    # The pre-ADR-030 measure (stripped length) after removing markup only; text without
    # markup counts exactly as before, so the pymupdf rollback keeps its old behaviour.
    # ADR-030 이전 척도(strip 후 길이)를 문법만 걷어낸 뒤 적용한다. 문법 없는 텍스트는
    # 이전과 똑같이 세므로 pymupdf 롤백은 옛 동작을 그대로 유지한다.
    page = _MD_TABLE_SEP_RE.sub("", page)
    page = _MD_TABLE_ROW_RE.sub(_table_row_text, page)
    page = _MD_HEADING_RE.sub("", page)
    page = page.replace("<br>", " ")
    return len(page.strip())


def _table_row_text(match: re.Match[str]) -> str:
    cells = (cell.strip() for cell in match.group(0).strip().strip("|").split("|"))
    return " ".join(cell for cell in cells if cell)


def _pdf_pages(path: Path) -> list[str]:
    """Per-page text: ODL merged page-by-page with PyMuPDF, or PyMuPDF alone.

    페이지별 텍스트: ODL을 PyMuPDF와 페이지 단위로 병합하거나, PyMuPDF만 쓴다.
    """
    if settings.pdf_parser != "odl":
        return _parse_pdf_pymupdf(path)
    try:
        odl_pages = _parse_pdf_odl(path)
    except ParserError as exc:
        # Type name only — the JAR's stderr can carry file paths.
        # 타입명만 — JAR stderr에는 파일 경로가 실릴 수 있다.
        cause = type(exc.__cause__).__name__ if exc.__cause__ else "ParserError"
        log.warning("pdf_odl_fallback", file=path.name, error=cause)
        return _parse_pdf_pymupdf(path)
    try:
        pymupdf_pages = _parse_pdf_pymupdf(path)
    except ParserError:
        return odl_pages
    return _merge_pages(path, odl_pages, pymupdf_pages)


def _merge_pages(path: Path, odl_pages: list[str], pymupdf_pages: list[str]) -> list[str]:
    # ODL keeps tables/headings but can drop a repeated-position paragraph; per page,
    # take PyMuPDF when ODL has clearly fewer words and PyMuPDF's text is not garbled.
    # ODL은 표·제목을 살리지만 같은 위치에 반복되는 문단을 버릴 수 있다. 페이지마다
    # ODL 단어가 확연히 적고 PyMuPDF 텍스트가 깨지지 않았으면 PyMuPDF를 쓴다.
    if len(odl_pages) != len(pymupdf_pages):
        log.warning("pdf_page_count_mismatch", file=path.name)
        return odl_pages
    merged: list[str] = []
    replaced = 0
    for odl_text, pymupdf_text in zip(odl_pages, pymupdf_pages, strict=True):
        odl_words = len(_WORD_RE.findall(odl_text))
        pymupdf_words = len(_WORD_RE.findall(pymupdf_text))
        if (
            not _is_garbled(pymupdf_text)
            and odl_words < settings.pdf_odl_min_word_ratio * pymupdf_words
        ):
            merged.append(pymupdf_text)
            replaced += 1
        else:
            merged.append(odl_text)
    if replaced:
        log.info("pdf_page_fallback", file=path.name, pages=replaced)
    return merged


def _is_garbled(text: str) -> bool:
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return False
    bad = sum(unicodedata.category(c) in ("Cc", "Co") for c in chars)
    return bad / len(chars) >= settings.pdf_garbled_char_ratio


def _parse_pdf_odl(path: Path) -> list[str]:
    # One JVM per call (~1 s); a private temp dir avoids <stem>.md collisions.
    # include_header_footer: ODL otherwise drops a paragraph that sits at the same spot
    # on every page as a "footer" (재등록 서류 활동 설명, 2026-10-01).
    # 호출마다 JVM 1개(~1초). 전용 임시 디렉터리로 <stem>.md 충돌을 피한다.
    # include_header_footer: 아니면 ODL이 매 페이지 같은 자리의 문단을 "꼬리말"로
    # 버린다 (재등록 서류 활동 설명, 2026-10-01).
    import opendataloader_pdf

    with tempfile.TemporaryDirectory() as out:
        try:
            opendataloader_pdf.convert(
                input_path=[str(path)],
                output_dir=out,
                format="markdown",
                quiet=True,
                image_output="off",
                include_header_footer=True,
                markdown_page_separator=_ODL_PAGE_SEPARATOR,
            )
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            raise ParserError(f"opendataloader-pdf failed on {path.name}") from exc
        produced = Path(out) / f"{path.stem}.md"
        if not produced.exists():
            raise ParserError(f"opendataloader-pdf wrote no markdown for {path.name}")
        markdown = produced.read_text(encoding="utf-8")
    return _split_odl_pages(markdown)


def _parse_pdf_pymupdf(path: Path) -> list[str]:
    import pymupdf

    try:
        # The `pymupdf` name is typed but Document.__init__ is not; strict mypy
        # flags the call (the old `fitz` name resolved to Any). Checked on 1.28.0 and 2.0.
        # `pymupdf` 이름은 타입이 있지만 Document.__init__엔 없어 strict mypy가 호출을
        # 잡는다(옛 `fitz` 이름은 Any였다). 1.28.0·2.0 둘 다 확인.
        with pymupdf.open(path) as doc:  # type: ignore[no-untyped-call]
            return [page.get_text("text") for page in doc]
    except Exception as exc:
        raise ParserError(f"pymupdf failed on {path.name}: {exc}") from exc


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
