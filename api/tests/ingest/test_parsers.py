"""Parser dispatch cases (Dajung.md §9).

파서 디스패치 케이스 (Dajung.md §9).
"""

from __future__ import annotations

import subprocess
import sys
import types
from pathlib import Path
from typing import Any

import pytest

from api.app.core.config import settings
from api.app.ingest import parsers
from api.app.ingest.parsers import (
    ParserEmptyError,
    UnsupportedFormatError,
    _split_odl_pages,
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


def test_pdf_pages_extracted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Pinned to PyMuPDF so the result never depends on whether Java is installed.
    # Java 설치 여부에 결과가 좌우되지 않도록 PyMuPDF로 고정한다.
    monkeypatch.setattr(settings, "pdf_parser", "pymupdf")
    # Build a real 2-page pdf with pymupdf — no external service needed.
    # pymupdf로 실제 2페이지 pdf를 만든다 — 외부 서비스 불필요.
    import pymupdf

    target = tmp_path / "two_pages.pdf"
    # ASCII text — the default pdf base font cannot render Hangul.
    # ASCII 텍스트 — pdf 기본 폰트는 한글을 렌더링하지 못한다.
    with pymupdf.open() as doc:  # type: ignore[no-untyped-call]
        for text in ("first page content. " * 10, "second page content. " * 10):
            page = doc.new_page()
            page.insert_text((72, 72), text)
        doc.save(str(target))

    parsed = parse_file(target)
    assert parsed.kind == "pdf"
    assert parsed.pages is not None and len(parsed.pages) == 2
    assert "first page" in parsed.pages[0]


def test_no_legacy_fitz_import_in_app_code() -> None:
    # PyMuPDF 2.0 deprecates the `fitz` name (FutureWarning, removal announced).
    # A source scan, not a warnings check: the warning fires once per process.
    # PyMuPDF 2.0은 `fitz` 이름을 폐기 예정으로 바꿨다(FutureWarning, 제거 예고).
    # 경고는 프로세스당 한 번만 나므로 경고 검사가 아니라 소스 검사로 막는다.
    import re

    app_dir = Path(__file__).resolve().parents[2] / "app"
    offenders = [
        path.relative_to(app_dir).as_posix()
        for path in app_dir.rglob("*.py")
        if re.search(r"^\s*(import fitz|from fitz )", path.read_text(encoding="utf-8"), re.M)
    ]
    assert offenders == []


def test_split_odl_pages_keeps_every_page_including_empty() -> None:
    # ODL writes the separator before every page, page 1 included (checked on v2.5.11 and v2.5.16).
    # ODL은 1페이지를 포함해 모든 페이지 앞에 구분자를 쓴다 (v2.5.11·2.5.16에서 확인).
    markdown = (
        "<!-- dajung-page 1 -->\n\n# alpha\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n"
        "<!-- dajung-page 2 -->\n\n"
        "<!-- dajung-page 3 -->\n\ngamma text\n\n"
    )
    assert _split_odl_pages(markdown) == [
        "# alpha\n\n| a | b |\n|---|---|\n| 1 | 2 |",
        "",
        "gamma text",
    ]


def test_split_odl_pages_without_separator_is_one_page() -> None:
    assert _split_odl_pages("only text\n") == ["only text"]


def _real_pdf(tmp_path: Path, pages: tuple[str, ...]) -> Path:
    import pymupdf

    target = tmp_path / "doc.pdf"
    with pymupdf.open() as doc:  # type: ignore[no-untyped-call]
        for text in pages:
            page = doc.new_page()
            if text:
                page.insert_text((72, 72), text)
        doc.save(str(target))
    return target


def _fake_odl(
    monkeypatch: pytest.MonkeyPatch, markdown: str = "", exc: BaseException | None = None
) -> list[dict[str, Any]]:
    # Stands in for the JAR: writes <stem>.md into output_dir like v2.5.11 and v2.5.16 do.
    # JAR 대역: v2.5.11·2.5.16처럼 output_dir에 <stem>.md를 쓴다.
    calls: list[dict[str, Any]] = []

    def convert(**kwargs: Any) -> None:
        calls.append(kwargs)
        if exc is not None:
            raise exc
        out = Path(kwargs["output_dir"])
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{Path(kwargs['input_path'][0]).stem}.md").write_text(markdown, encoding="utf-8")

    monkeypatch.setitem(sys.modules, "opendataloader_pdf", types.SimpleNamespace(convert=convert))
    return calls


def _odl_md(*pages: str) -> str:
    return "".join(f"<!-- dajung-page {n} -->\n\n{body}\n\n" for n, body in enumerate(pages, 1))


_TABLE_PAGE = "# 인수인계 확인서\n\n| 항목 | 담당 |\n|---|---|\n| 통장 | 총무 |"
_TABLE_PAGE_PLAIN = "인수인계 확인서 항목 담당 통장 총무"
# Over _PDF_MIN_CHARS (50) on its own, so single-page tests exercise the merge, not docling.
# 단독으로도 _PDF_MIN_CHARS(50)를 넘겨, 1페이지 테스트가 docling이 아니라 병합을 탄다.
_ACTIVITY = (
    "활동 설명: 가상의 예시 문단입니다. 정기 다회에서 세 가지 찻잎을 차례로 우리고, "
    "찻잎마다 우린 시간과 물 온도를 기록했습니다."
)


def test_odl_is_default_and_keeps_tables_and_pages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "pdf_parser", "odl")
    calls = _fake_odl(monkeypatch, _odl_md(_TABLE_PAGE, _ACTIVITY))
    monkeypatch.setattr(parsers, "_parse_pdf_pymupdf", lambda path: [_TABLE_PAGE_PLAIN, _ACTIVITY])
    parsed = parse_file(_real_pdf(tmp_path, ("x",)))

    assert parsed.kind == "pdf"
    assert parsed.pages == [_TABLE_PAGE, _ACTIVITY]
    assert parsed.text == "\n\n".join(parsed.pages)
    kw = calls[0]
    assert kw["format"] == "markdown"
    assert kw["image_output"] == "off"
    assert kw["include_header_footer"] is True
    assert kw["markdown_page_separator"] == "<!-- dajung-page %page-number% -->"
    assert kw["quiet"] is True


def test_page_where_odl_drops_words_uses_pymupdf_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The 2026 재등록 서류 case: ODL lost the 활동 설명 paragraph on some pages.
    # 2026 재등록 서류 사례: ODL이 일부 페이지에서 활동 설명 문단을 잃었다.
    monkeypatch.setattr(settings, "pdf_parser", "odl")
    _fake_odl(monkeypatch, _odl_md(_TABLE_PAGE, "활동 사진"))
    monkeypatch.setattr(
        parsers, "_parse_pdf_pymupdf", lambda path: [_TABLE_PAGE_PLAIN, "활동 사진\n" + _ACTIVITY]
    )
    parsed = parse_file(_real_pdf(tmp_path, ("x",)))

    assert parsed.pages == [_TABLE_PAGE, "활동 사진\n" + _ACTIVITY]


def test_garbled_pymupdf_page_never_replaces_odl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Font-decoding failure: PyMuPDF yields control chars plus ASCII noise, ODL the real text.
    # 폰트 디코딩 실패: PyMuPDF는 제어문자와 ASCII 잡음, ODL은 실제 본문을 낸다.
    monkeypatch.setattr(settings, "pdf_parser", "odl")
    _fake_odl(monkeypatch, _odl_md(_ACTIVITY))
    noise = "\x01\x02\x03 ab cd ef gh ij kl mn op qr st uv wx yz " * 20
    monkeypatch.setattr(parsers, "_parse_pdf_pymupdf", lambda path: [noise])
    parsed = parse_file(_real_pdf(tmp_path, ("x",)))

    assert parsed.pages == [_ACTIVITY]


def test_page_count_mismatch_keeps_odl(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "pdf_parser", "odl")
    _fake_odl(monkeypatch, _odl_md(_ACTIVITY))
    monkeypatch.setattr(parsers, "_parse_pdf_pymupdf", lambda path: [_ACTIVITY, _ACTIVITY])
    parsed = parse_file(_real_pdf(tmp_path, ("x",)))

    assert parsed.pages == [_ACTIVITY]


@pytest.mark.parametrize(
    "exc",
    [
        subprocess.CalledProcessError(1, ["java"]),
        FileNotFoundError("java"),
    ],
)
def test_odl_failure_falls_back_to_pymupdf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, exc: BaseException
) -> None:
    # No Java or a JAR crash must not lose the document — plain text still arrives.
    # Java 부재나 JAR 오류로 문서를 잃으면 안 된다 — 평문은 그대로 들어온다.
    monkeypatch.setattr(settings, "pdf_parser", "odl")
    _fake_odl(monkeypatch, exc=exc)
    parsed = parse_file(_real_pdf(tmp_path, ("first page content. " * 10, "second page. " * 10)))

    assert parsed.pages is not None and len(parsed.pages) == 2
    assert "first page" in parsed.pages[0]


def test_pymupdf_setting_never_calls_odl(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "pdf_parser", "pymupdf")
    calls = _fake_odl(monkeypatch, _odl_md(_TABLE_PAGE))
    parsed = parse_file(_real_pdf(tmp_path, ("first page content. " * 10,)))

    assert calls == []
    assert parsed.pages is not None and "first page" in parsed.pages[0]


def test_text_less_odl_output_still_goes_to_docling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A scan yields page markers only; the docling fallback path is unchanged.
    # 스캔본은 페이지 표식만 나온다. docling 폴백 경로는 그대로다.
    monkeypatch.setattr(settings, "pdf_parser", "odl")
    _fake_odl(monkeypatch, "<!-- dajung-page 1 -->\n\n")
    monkeypatch.setattr(parsers, "_parse_pdf_docling", lambda path: "")
    with pytest.raises(ParserEmptyError):
        parse_file(_real_pdf(tmp_path, ("",)))


@pytest.mark.external
def test_real_opendataloader_jar_splits_pages(tmp_path: Path) -> None:
    # Needs Java 11+ and the opendataloader-pdf wheel; run with `pytest -m external`.
    # Java 11+와 opendataloader-pdf wheel이 필요하다. `pytest -m external`로 실행.
    from api.app.ingest.parsers import _parse_pdf_odl

    pages = _parse_pdf_odl(_real_pdf(tmp_path, ("alpha page one", "", "gamma page three")))
    assert len(pages) == 3
    assert "alpha" in pages[0] and pages[1] == "" and "gamma" in pages[2]
