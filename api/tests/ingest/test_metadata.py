"""Metadata mapping, semester inference, frontmatter (Dajung.md §9).

메타 매핑, 학기 추론, frontmatter (Dajung.md §9).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from api.app.graph.nodes.retrieve_handover import HANDOVER_DOC_TYPES
from api.app.ingest.chunker import Chunk
from api.app.ingest.metadata import (
    CATEGORY_MAP,
    CsvRow,
    build_payload,
    category_meta,
    csv_key,
    csv_row_for,
    doc_id_for,
    infer_semester,
    load_csv_index,
    parse_frontmatter,
)

_CSV_HEADER = "번호,파일명,폴더,상대경로,확장자,카테고리,학기,크기(KB),수정일시,비고\n"


def _chunk() -> Chunk:
    return Chunk(text="본문", chunk_index=0, total_chunks=1, locator="sec:0")


# Every leaf the 2026-09-14 CSV uses, with its Data_prep.md §F-3 doc_type.
# 2026-09-14 CSV가 쓰는 모든 잎과 Data_prep.md §F-3의 doc_type.
_LEAF_DOC_TYPES = {
    "지식/세미나-동양차": "tea_knowledge",
    "지식/세미나-서양차": "tea_knowledge",
    "지식/세미나-커피": "coffee_knowledge",
    "지식/다도-다례": "tea_knowledge",
    "지식/구매처": "coffee_knowledge",
    "지식/기구-용품": "equipment",
    "운영/회의록": "minutes",
    "운영/인수인계": "handover",
    "운영/OT-오리엔테이션": "handover",
    "운영/운영노하우": "handover",
    "운영/회칙": "operation_rule",
    "운영/동방-규칙": "operation_rule",
    "운영/활동계획-일정": "misc",
    "운영/활동보고": "misc",
    "운영/체크리스트": "checklist",
    "행정/재등록": "admin_doc",
    "행정/지원금-보조금": "admin_doc",
    "행정/동연-대외제출": "admin_doc",
    "행정/가이드-공지": "admin_doc",
    "행정/시설-출입": "admin_doc",
    "재정/예산안": "budget",
    "재정/장부-결산": "budget",
    "재정/영수증-증빙": "budget",
    "홍보/부스": "misc",
    "홍보/온라인-에타": "misc",
    "홍보/브랜딩-로고": "misc",
    "교류/연합-차동연": "misc",
    "교류/주점-공동행사": "misc",
    "교류/제휴-제안": "admin_doc",
    "교류/홈커밍-OB": "misc",
    "회원/명단-명부": "misc",
    "회원/신청서-응답": "misc",
    "회원/회비": "misc",
    "기록/활동사진": "misc",
    "기록/채팅기록": "misc",
}


def test_category_map_covers_every_csv_leaf() -> None:
    assert set(CATEGORY_MAP) == set(_LEAF_DOC_TYPES)
    for category, doc_type in _LEAF_DOC_TYPES.items():
        assert CATEGORY_MAP[category][0] == doc_type, category


def test_handover_leaves_reach_the_handover_route() -> None:
    # The flat-key map sent 운영/인수인계 to misc, outside retrieve_handover's filter.
    # 평면 키 맵은 운영/인수인계를 misc로 보내 retrieve_handover 필터 밖에 두었다.
    for leaf in ("운영/인수인계", "운영/회의록", "운영/회칙", "운영/체크리스트", "재정/예산안"):
        assert category_meta(leaf)[0] in HANDOVER_DOC_TYPES, leaf


@pytest.mark.parametrize(
    ("category", "expected"),
    [
        ("운영/새소분류", ("misc", False, "low")),
        ("행정/새소분류", ("admin_doc", False, "low")),
        ("회원/새소분류", ("misc", False, "high")),
        ("기록/새소분류", ("misc", False, "high")),
        ("새대분류/무언가", ("misc", False, "low")),
        ("", ("misc", False, "low")),
    ],
)
def test_unknown_leaf_falls_back_to_parent_then_default(
    category: str, expected: tuple[str, bool, str]
) -> None:
    assert category_meta(category) == expected


def test_member_roster_open_but_sensitive() -> None:
    # 2026-07-07 policy: executives-only tool — rosters are open to all staff.
    # 2026-07-07 정책: 운영진 전용 도구 — 명단은 전 staff에게 공개.
    row = CsvRow(category="회원/명단-명부", folder="", modified="2025-03-24 11:03")
    payload = build_payload(Path("24-1 다정회원명단.xlsx"), row, _chunk(), "h")
    assert payload["restricted"] is False
    assert payload["sensitivity"] == "high"  # log-masking still applies later


def test_chat_log_open_but_sensitive() -> None:
    row = CsvRow(category="기록/채팅기록", folder="", modified="")
    payload = build_payload(Path("KakaoTalk_group.txt"), row, _chunk(), "h")
    assert payload["restricted"] is False
    assert payload["sensitivity"] == "high"


def test_no_category_is_restricted_by_default() -> None:
    # Only incidents are withheld, and those are excluded before indexing
    # (ADR-013) — so no CATEGORY_MAP row may set restricted=True.
    # 차단 대상은 사건사고뿐이고 그건 인덱싱 전에 제외된다(ADR-013) —
    # 따라서 CATEGORY_MAP 어떤 행도 restricted=True면 안 된다.
    for category, (_, restricted, _) in CATEGORY_MAP.items():
        assert restricted is False, category


def test_coffee_seminar_leaf_is_coffee_knowledge() -> None:
    row = CsvRow(category="지식/세미나-커피", folder="", modified="")
    payload = build_payload(Path("커피 세미나 check list.docx"), row, _chunk(), "h")
    assert payload["doc_type"] == "coffee_knowledge"


def test_semester_patterns() -> None:
    assert infer_semester("2025-1 동양차 세미나.pdf") == "2025-1"
    assert infer_semester("25-1학기 다정 신청서.xlsx") == "2025-1"
    assert infer_semester("24.03.16회의록.docx") == "2024-1"
    assert infer_semester("무패턴파일.docx") is None


def test_csv_semester_wins_over_filename() -> None:
    assert infer_semester("2025-1 동양차 세미나.pdf", "2019-2") == "2019-2"
    assert infer_semester("무패턴파일.docx", "2021-1") == "2021-1"


def test_modified_timestamp_is_never_a_semester_source() -> None:
    # The 2026 server copy made every mtime meaningless (Data_prep.md §F-4).
    # 2026년 서버 복사로 모든 mtime이 무의미해졌다 (Data_prep.md §F-4).
    assert infer_semester("무패턴파일.docx", "2024-09-23 21:57") is None
    row = CsvRow(category="운영/회의록", folder="", modified="2026-09-14 10:00", semester="")
    payload = build_payload(Path("무패턴파일.docx"), row, _chunk(), "h")
    assert payload["semester"] is None
    assert payload["last_modified"] == "2026-09-14 10:00"


def test_csv_semester_reaches_payload() -> None:
    row = CsvRow(category="운영/회의록", folder="", modified="", semester="2019-1")
    payload = build_payload(Path("2025-2 회의록.docx"), row, _chunk(), "h")
    assert payload["semester"] == "2019-1"


def test_csv_index_keyed_by_relative_path(tmp_path: Path) -> None:
    csv_path = tmp_path / "list.csv"
    csv_path.write_text(
        _CSV_HEADER
        + "1,회의록.docx,2019 다정,추가\\2019 다정\\회의록.docx,.docx,운영/회의록,2019-1,1,,\n"
        + "2,회의록.docx,2021 다정,추가\\2021 다정\\회의록.docx,.docx,운영/회의록,2021-2,1,,\n"
        + "3,2025-2 인수인계.pdf,(최상위),2025-2 인수인계.pdf,.pdf,운영/인수인계,2025-2,1,,\n",
        encoding="utf-8-sig",
    )
    index = load_csv_index(csv_path)

    # Same filename in two folders stays two rows (filename keys collapsed them).
    # 두 폴더의 같은 파일명이 두 행으로 남는다 (파일명 키는 하나로 합쳤다).
    assert index["추가/2019 다정/회의록.docx"].semester == "2019-1"
    assert index["추가/2021 다정/회의록.docx"].semester == "2021-2"
    assert index["2025-2 인수인계.pdf"].category == "운영/인수인계"


def test_csv_row_for_resolves_under_data_dir_only(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    (data_dir / "추가" / "2019 다정").mkdir(parents=True)
    inside = data_dir / "추가" / "2019 다정" / "회의록.docx"
    index = {"추가/2019 다정/회의록.docx": CsvRow("운영/회의록", "2019 다정", "", "2019-1")}

    assert csv_row_for(index, inside, data_dir) == index["추가/2019 다정/회의록.docx"]
    assert csv_row_for(index, tmp_path / "elsewhere" / "회의록.docx", data_dir) is None
    assert csv_row_for(index, data_dir / "회의록.docx", data_dir) is None


def test_csv_key_normalizes_separators() -> None:
    assert csv_key("추가\\2019 다정\\회의록.docx") == "추가/2019 다정/회의록.docx"
    assert csv_key("./knowledge/tea/a.md") == "knowledge/tea/a.md"


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
