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
