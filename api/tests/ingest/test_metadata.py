"""Metadata mapping, semester inference, frontmatter (Dajung.md §9).

메타 매핑, 학기 추론, frontmatter (Dajung.md §9).
"""

from __future__ import annotations

from pathlib import Path

from api.app.ingest.chunker import Chunk
from api.app.ingest.metadata import (
    CATEGORY_MAP,
    CsvRow,
    build_payload,
    doc_id_for,
    infer_semester,
    parse_frontmatter,
)


def _chunk() -> Chunk:
    return Chunk(text="본문", chunk_index=0, total_chunks=1, locator="sec:0")


def test_category_map_covers_all_rows() -> None:
    expected = {
        "인수인계": "handover",
        "회의록": "minutes",
        "예산안": "budget",
        "세미나-교육자료": "tea_knowledge",
        "재등록-행정서류": "admin_doc",
        "지원금-보조금 신청": "admin_doc",
        "행정서류-가이드": "admin_doc",
        "제휴-제안서": "admin_doc",
        "회원명단-신청서": "misc",
        "채팅기록": "misc",
        "카페탐방": "misc",
        "동방투어": "misc",
        "홍보부스": "misc",
        "활동기록-일정": "misc",
        "소모임-네트워킹": "misc",
    }
    for category, doc_type in expected.items():
        assert CATEGORY_MAP[category][0] == doc_type, category


def test_member_roster_is_restricted_high() -> None:
    row = CsvRow(category="회원명단-신청서", folder="", modified="2025-03-24 11:03")
    payload = build_payload(Path("24-1 다정회원명단.xlsx"), row, _chunk(), "h")
    assert payload["restricted"] is True
    assert payload["sensitivity"] == "high"


def test_chat_log_is_restricted() -> None:
    row = CsvRow(category="채팅기록", folder="", modified="")
    payload = build_payload(Path("KakaoTalk_group.txt"), row, _chunk(), "h")
    assert payload["restricted"] is True


def test_coffee_seminar_reclassified() -> None:
    row = CsvRow(category="세미나-교육자료", folder="", modified="")
    payload = build_payload(Path("커피 세미나 check list.docx"), row, _chunk(), "h")
    assert payload["doc_type"] == "coffee_knowledge"


def test_semester_patterns() -> None:
    assert infer_semester("2025-1 동양차 세미나.pdf", "") == "2025-1"
    assert infer_semester("25-1학기 다정 신청서.xlsx", "") == "2025-1"
    assert infer_semester("24.03.16회의록.docx", "") == "2024-1"
    assert infer_semester("무패턴파일.docx", "2024-09-23 21:57") == "2024-2"
    assert infer_semester("무패턴파일.docx", "") is None


def test_doc_id_deterministic() -> None:
    assert doc_id_for("data/a.md") == doc_id_for("data/a.md")
    assert doc_id_for("data/a.md") != doc_id_for("data/b.md")


def test_frontmatter_parse_and_override() -> None:
    text = "---\ndoc_type: equipment\nrestricted: true\nsemester: 2026-1\n---\n# 개완\n본문"
    meta, body = parse_frontmatter(text)
    assert meta["doc_type"] == "equipment"
    assert body.startswith("# 개완")

    payload = build_payload(
        Path("data/knowledge/equipment/개완.md"), None, _chunk(), "h", frontmatter=meta
    )
    assert payload["doc_type"] == "equipment"
    assert payload["restricted"] is True
    assert payload["semester"] == "2026-1"


def test_no_frontmatter_passthrough() -> None:
    meta, body = parse_frontmatter("# 그냥 문서\n본문")
    assert meta == {} and body.startswith("# 그냥")
