"""Term list for header wording: loading, unify step, keep list. Synthetic text only.

헤더 용어 사전: 로드, 통일 단계, 유지 목록. 합성 텍스트만 사용.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from api.app.ingest.terms import Terms, load_terms, parse_terms

_RULES = {
    "unify": {"동아리방": ["동아리실", "동방"]},
    "conditional": [
        {
            "wrong": "사무실",
            "right": "동아리방",
            "when_source_has": ["동아리방", "동아리실", "동방"],
        }
    ],
    "protect": ["동방미인"],
    "keep": ["집행부", "동비", "연합다회", "다회", "홈커밍데이"],
}


@pytest.fixture
def terms() -> Terms:
    return parse_terms(_RULES)


# --- unify: aliases ---


def test_unify_replaces_aliases_with_canonical(terms: Terms) -> None:
    out = terms.unify("동아리실 청소와 동방 정리 안내.", source="")
    assert out == "동아리방 청소와 동아리방 정리 안내."


def test_unify_leaves_protected_word_alone(terms: Terms) -> None:
    out = terms.unify("동방미인 시음과 동방 정리.", source="")
    assert out == "동방미인 시음과 동아리방 정리."


def test_unify_is_idempotent(terms: Terms) -> None:
    once = terms.unify("동방에서 동방미인을 우린다. 동아리방 규칙.", source="")
    assert terms.unify(once, source="") == once


# --- unify: conditional 사무실 ---


def test_conditional_replaces_when_source_names_a_room(terms: Terms) -> None:
    out = terms.unify("사무실 사용 규칙 부분.", source="동방 퇴실 시 전등을 끈다.")
    assert out == "동아리방 사용 규칙 부분."


def test_conditional_skips_when_source_has_no_room_word(terms: Terms) -> None:
    out = terms.unify("사무실 사용 규칙 부분.", source="정규활동 일정 안내.")
    assert out == "사무실 사용 규칙 부분."


def test_conditional_skips_when_source_itself_says_wrong_word(terms: Terms) -> None:
    out = terms.unify("사무실 방문 안내.", source="동아리방 대신 학생회 사무실에서 받는다.")
    assert out == "사무실 방문 안내."


def test_protected_word_in_source_does_not_count_as_room(terms: Terms) -> None:
    out = terms.unify("사무실 이야기.", source="동방미인 우리는 법.")
    assert out == "사무실 이야기."


# --- keep list ---


def test_to_keep_finds_acronyms_then_club_terms(terms: Terms) -> None:
    source = "OT 자료. SNS 홍보와 집행부 회의, 동비 납부 안내."
    assert terms.to_keep(source, max_acronyms=5, max_terms=3) == ["OT", "SNS", "동비", "집행부"]


def test_to_keep_ignores_single_letters_and_mixed_case(terms: Terms) -> None:
    source = "A안과 B안, Teams 회의, iOS 앱, Q1."
    assert terms.to_keep(source, max_acronyms=5, max_terms=3) == ["Q1"]


def test_to_keep_ignores_acronyms_inside_longer_words(terms: Terms) -> None:
    assert terms.to_keep("ABCdef 문서", max_acronyms=5, max_terms=3) == []


def test_to_keep_respects_caps(terms: Terms) -> None:
    source = "AA BB CC DD 집행부 동비 연합다회 홈커밍데이"
    assert terms.to_keep(source, max_acronyms=2, max_terms=1) == ["AA", "BB", "동비"]


def test_to_keep_skips_term_seen_only_inside_longer_term(terms: Terms) -> None:
    assert terms.to_keep("연합다회 준비", max_acronyms=5, max_terms=3) == ["연합다회"]
    assert terms.to_keep("연합다회와 다회 준비", max_acronyms=5, max_terms=3) == [
        "다회",
        "연합다회",
    ]


def test_to_keep_lists_each_term_once(terms: Terms) -> None:
    assert terms.to_keep("OT OT 동비 동비", max_acronyms=5, max_terms=3) == ["OT", "동비"]


def test_to_keep_empty_when_nothing_found(terms: Terms) -> None:
    assert terms.to_keep("차 우리는 온도 안내.", max_acronyms=5, max_terms=3) == []


# --- validation ---


@pytest.mark.parametrize(
    "bad",
    [
        {"unify": {"동아리방": ["동아리방"]}},
        {"unify": {"동아리방": ["동방"], "다른방": ["동방"]}},
        {"unify": {"동아리방": ["동방"], "동방": ["동실"]}},
        {"unify": {"동아리방": [""]}},
        {"keep": ["  "]},
        {"conditional": [{"wrong": "사무실", "right": "동아리방", "when_source_has": []}]},
        {"unknown_section": []},
    ],
)
def test_parse_terms_rejects_bad_rules(bad: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        parse_terms(bad)


def test_load_terms_reads_yaml(tmp_path: Path) -> None:
    path = tmp_path / "terms.yaml"
    path.write_text("unify:\n  동아리방: [동방]\nkeep: [동비]\n", encoding="utf-8")
    terms = load_terms(path)
    assert terms.unify("동방", source="") == "동아리방"
    assert terms.keep == ("동비",)


def test_load_terms_empty_file_means_no_rules(tmp_path: Path) -> None:
    path = tmp_path / "terms.yaml"
    path.write_text("", encoding="utf-8")
    terms = load_terms(path)
    assert terms.unify("동방 사무실", source="동방") == "동방 사무실"
    assert terms.keep == ()


def test_load_terms_reports_file_on_bad_rules(tmp_path: Path) -> None:
    path = tmp_path / "terms.yaml"
    path.write_text("keep: 동비\n", encoding="utf-8")
    with pytest.raises(ValueError, match="terms.yaml"):
        load_terms(path)


# --- the shipped file (catches edit mistakes in prompts/terms.yaml) ---


def test_shipped_terms_file_loads_with_expected_rules() -> None:
    terms = load_terms(Path("prompts/terms.yaml"))
    assert terms.unify("동아리실과 동방, 동방미인", source="") == "동아리방과 동아리방, 동방미인"
    assert terms.unify("사무실", source="동방 정리") == "동아리방"
    assert terms.unify("사무실", source="정규활동") == "사무실"
    assert "집행부" in terms.keep
