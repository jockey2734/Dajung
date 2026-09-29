"""Exclusion rule cases (Dajung.md §9).

제외 규칙 케이스 (Dajung.md §9).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from api.app.ingest.exclude import is_excluded


def test_incident_path_excluded() -> None:
    excluded, reason = is_excluded(Path("data/사건사고/2024_사건.docx"))
    assert excluded and reason == "incident"


def test_incident_nested_path_excluded() -> None:
    excluded, reason = is_excluded(Path("data/자료/사건사고/메모.txt"))
    assert excluded and reason == "incident"


def test_office_lock_file_excluded() -> None:
    excluded, reason = is_excluded(Path("data/~$ 운영진 인수인계서.docx"))
    assert excluded and reason == "tempfile"


def test_tmp_extension_excluded() -> None:
    excluded, reason = is_excluded(Path("data/~WRL1730.TMP"))
    assert excluded and reason == "tempfile"


def test_image_extension_excluded() -> None:
    for name in ("로고.png", "부스.JPG", "캡처.jfif"):
        excluded, reason = is_excluded(Path("data") / name)
        assert excluded and reason == "image", name


@pytest.mark.parametrize("category", ["홍보/브랜딩-로고", "기록/활동사진"])
def test_csv_image_category_excluded(category: str) -> None:
    excluded, reason = is_excluded(Path("data/무언가.pdf"), csv_category=category)
    assert excluded and reason == "image"


def test_hidden_file_excluded() -> None:
    excluded, reason = is_excluded(Path("data/.ingest_manifest.json"))
    assert excluded and reason == "hidden"


def test_trash_directory_excluded() -> None:
    excluded, reason = is_excluded(Path("data/.trash/deleted-guide.md"))
    assert excluded and reason == "trash"


def test_normal_files_pass() -> None:
    for name in ("25-1 다정 예산안.xlsx", "회의록.docx", "인수인계.pdf", "guide.md"):
        excluded, reason = is_excluded(Path("data") / name, csv_category="예산안")
        assert not excluded and reason == "", name


def test_incident_beats_other_rules() -> None:
    # Rule order: incident wins even for an image inside the incident dir.
    # 규칙 순서: 사건사고 안의 이미지도 사유는 incident다.
    excluded, reason = is_excluded(Path("data/사건사고/증거.png"))
    assert excluded and reason == "incident"


@pytest.mark.parametrize(
    "category",
    [
        "회원/명단-명부",
        "회원/신청서-응답",
        "회원/회비",
        "회원/새소분류",
        "기록/채팅기록",
        "재정/영수증-증빙",
    ],
)
def test_csv_do_not_ingest_category_excluded(category: str) -> None:
    # Data_prep.md §F-3 marks 회원/·기록/ "ingest 제외"; §F-5 bans receipt originals.
    # Data_prep.md §F-3은 회원/·기록/을 ingest 제외로, §F-5는 영수증 원문 금지로 정했다.
    excluded, reason = is_excluded(Path("data/무언가.xlsx"), csv_category=category)
    assert excluded and reason == "csv_category"


@pytest.mark.parametrize("category", ["재정/예산안", "재정/장부-결산", "운영/회의록"])
def test_other_finance_and_ops_leaves_pass(category: str) -> None:
    excluded, reason = is_excluded(Path("data/무언가.xlsx"), csv_category=category)
    assert not excluded and reason == ""


@pytest.mark.parametrize(
    "note",
    [
        "PII-정제필요",
        "중복사본",
        "이미지-ingest제외",
        "원본hwp-파서미지원",
        "동명이본;PII-정제필요",
        "중복사본;원본hwp-파서미지원;PII-정제필요",
        " 동명이본 ; 중복사본 ",
    ],
)
def test_csv_note_tag_excluded(note: str) -> None:
    excluded, reason = is_excluded(
        Path("data/무언가.docx"), csv_category="운영/회의록", csv_note=note
    )
    assert excluded and reason == "csv_note"


@pytest.mark.parametrize("note", ["", "동명이본", "hwp변환본", "분류확인필요", "PII-정제필요-완료"])
def test_benign_or_unknown_note_passes(note: str) -> None:
    # Tags match exactly; a longer tag that merely contains one is not excluded.
    # 태그는 정확히 일치해야 한다 — 포함만 하는 더 긴 태그는 제외하지 않는다.
    excluded, reason = is_excluded(
        Path("data/무언가.docx"), csv_category="운영/회의록", csv_note=note
    )
    assert not excluded and reason == ""


def test_incident_beats_csv_rules() -> None:
    excluded, reason = is_excluded(
        Path("data/사건사고/명부.xlsx"), csv_category="회원/명단-명부", csv_note="PII-정제필요"
    )
    assert excluded and reason == "incident"
