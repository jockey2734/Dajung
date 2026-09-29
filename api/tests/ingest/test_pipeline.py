"""Pipeline dry-run behavior — fully offline (Dajung.md §9).

파이프라인 dry-run 동작 — 완전 오프라인 (Dajung.md §9).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from api.app.ingest.pipeline import InventoryMissingError, run_ingest, run_ingest_file


@pytest.fixture(autouse=True)
def _isolate_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Point manifest/CSV at the temp dir so real project files are untouched.
    # 매니페스트·CSV를 임시 경로로 돌려 실제 프로젝트 파일을 건드리지 않는다.
    monkeypatch.setenv("DAJUNG_MANIFEST_PATH", str(tmp_path / "manifest.json"))
    monkeypatch.setenv("DAJUNG_CSV_PATH", str(tmp_path / "no_such.csv"))
    from api.app.core import config

    monkeypatch.setattr(config, "settings", config.Settings(_env_file=None))  # type: ignore[call-arg]
    # Modules imported `settings` by value — patch their references too.
    # 모듈들이 settings를 값으로 임포트했으므로 참조도 함께 패치한다.
    from api.app.ingest import chunker, pipeline

    monkeypatch.setattr(pipeline, "settings", config.settings)
    monkeypatch.setattr(chunker, "settings", config.settings)


def test_dry_run_counts_and_no_manifest(tmp_docs: Path, tmp_path: Path) -> None:
    report = run_ingest(tmp_docs, dry_run=True)
    assert report.scanned == 2  # guide.md + note.txt
    assert report.upserted_chunks == 0
    assert report.errors == []
    assert not (tmp_path / "manifest.json").exists()


def test_dry_run_excludes(tmp_docs: Path) -> None:
    (tmp_docs / "~$lock.docx").write_bytes(b"x")
    (tmp_docs / "로고.png").write_bytes(b"x")
    incident = tmp_docs / "사건사고"
    incident.mkdir()
    (incident / "사건.txt").write_text("비밀", encoding="utf-8")

    report = run_ingest(tmp_docs, dry_run=True)
    assert report.excluded["tempfile"] == 1
    assert report.excluded["image"] == 1
    assert report.excluded["incident"] == 1
    assert report.scanned == 2


def test_parse_error_recorded_not_raised(tmp_docs: Path) -> None:
    (tmp_docs / "미지원.hwp").write_bytes(b"x")
    report = run_ingest(tmp_docs, dry_run=True)
    assert len(report.errors) == 1
    assert report.errors[0][0] == "미지원.hwp"
    assert "UnsupportedFormatError" in report.errors[0][1]
    # Other files still processed.
    # 다른 파일은 계속 처리된다.
    assert report.scanned == 3


def test_summary_format(tmp_docs: Path) -> None:
    report = run_ingest(tmp_docs, dry_run=True)
    text = report.summary()
    assert "scanned: 2" in text and "errors: 0" in text


def test_single_file_dry_run_only_scans_target(tmp_docs: Path) -> None:
    report = run_ingest_file(tmp_docs / "guide.md", dry_run=True)
    assert report.scanned == 1
    assert report.errors == []


def test_csv_lookup_uses_path_under_data_dir_not_filename(
    tmp_docs: Path, tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Two files named note.txt; the CSV marks only the one under 기록/ as a photo-category
    # row. A filename-keyed lookup would exclude both.
    # note.txt가 두 개이고 CSV는 기록/ 아래 것만 사진 분류로 표시한다. 파일명 키
    # 조회였다면 둘 다 제외됐다.
    from api.app.core import config

    (tmp_docs / "기록").mkdir()
    (tmp_docs / "기록" / "note.txt").write_text("사진 설명\n", encoding="utf-8")
    csv_path = tmp_path_factory.mktemp("csv") / "list.csv"
    csv_path.write_text(
        "번호,파일명,폴더,상대경로,확장자,카테고리,학기,크기(KB),수정일시,비고\n"
        "1,note.txt,기록,기록\\note.txt,.txt,기록/활동사진,2019-1,1,,\n",
        encoding="utf-8-sig",
    )
    # The autouse fixture points pipeline.settings at this same config.settings object.
    # autouse 픽스처가 pipeline.settings를 바로 이 config.settings 객체로 돌려놨다.
    monkeypatch.setattr(config.settings, "csv_path", csv_path)
    monkeypatch.setattr(config.settings, "data_dir", tmp_docs)

    report = run_ingest(tmp_docs, dry_run=True)

    assert report.excluded["image"] == 1
    assert report.scanned == 2  # guide.md + top-level note.txt


def test_csv_rules_keep_rosters_and_flagged_files_out(
    tmp_docs: Path, tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A whole-tree ingest must not index what the inventory marks "do not ingest" (S31-2).
    # 트리 전체 ingest도 목록이 ingest 제외로 표시한 것은 색인하지 않는다 (S31 정정 2).
    from api.app.core import config

    (tmp_docs / "회원").mkdir()
    (tmp_docs / "회원" / "명부.txt").write_text("합성 명부\n", encoding="utf-8")
    (tmp_docs / "운영").mkdir()
    (tmp_docs / "운영" / "회의.txt").write_text("합성 회의록\n", encoding="utf-8")
    (tmp_docs / "운영" / "정리본.txt").write_text("합성 정리본\n", encoding="utf-8")
    csv_path = tmp_path_factory.mktemp("csv") / "list.csv"
    csv_path.write_text(
        "번호,파일명,폴더,상대경로,확장자,카테고리,학기,크기(KB),수정일시,비고\n"
        "1,명부.txt,회원,회원\\명부.txt,.txt,회원/명단-명부,2019,1,,PII-정제필요\n"
        "2,회의.txt,운영,운영\\회의.txt,.txt,운영/회의록,2019,1,,PII-정제필요\n"
        "3,정리본.txt,운영,운영\\정리본.txt,.txt,운영/회의록,2019-2,1,,hwp변환본\n",
        encoding="utf-8-sig",
    )
    monkeypatch.setattr(config.settings, "csv_path", csv_path)
    monkeypatch.setattr(config.settings, "data_dir", tmp_docs)

    report = run_ingest(tmp_docs, dry_run=True)

    assert report.excluded["csv_category"] == 1  # the 회원 category wins over its PII tag
    assert report.excluded["csv_note"] == 1
    assert report.scanned == 3  # guide.md + note.txt + 운영/정리본.txt


_INVENTORY_HEADER = "번호,파일명,폴더,상대경로,확장자,카테고리,학기,크기(KB),수정일시,비고\n"


@pytest.mark.parametrize("content", [None, _INVENTORY_HEADER])
def test_ingest_under_data_dir_refuses_without_inventory(
    tmp_docs: Path, monkeypatch: pytest.MonkeyPatch, content: str | None
) -> None:
    # Missing or empty inventory under data/ = every CSV rule silently off → fail closed.
    # data/ 아래에서 목록이 없거나 비면 CSV 규칙이 조용히 꺼진다 → 중단한다.
    from api.app.core import config

    inventory = tmp_docs / "list.csv"
    if content is not None:
        inventory.write_text(content, encoding="utf-8-sig")
    monkeypatch.setattr(config.settings, "csv_path", inventory)
    monkeypatch.setattr(config.settings, "data_dir", tmp_docs)

    with pytest.raises(InventoryMissingError):
        run_ingest(tmp_docs, dry_run=True)
    with pytest.raises(InventoryMissingError):
        run_ingest_file(tmp_docs / "guide.md", dry_run=True)


def test_inventory_inside_data_dir_is_never_ingested(
    tmp_docs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The inventory is a parseable .csv listing every file name — skip it, count it.
    # 목록은 모든 파일명을 담은 파싱 가능한 .csv다 — 건너뛰고 집계한다.
    from api.app.core import config

    inventory = tmp_docs / "다정_파일목록.csv"
    inventory.write_text(
        _INVENTORY_HEADER + "1,note.txt,(최상위),note.txt,.txt,운영/회의록,2019,1,,\n",
        encoding="utf-8-sig",
    )
    monkeypatch.setattr(config.settings, "csv_path", inventory)
    monkeypatch.setattr(config.settings, "data_dir", tmp_docs)

    report = run_ingest(tmp_docs, dry_run=True)

    assert report.excluded["inventory"] == 1
    assert report.scanned == 2  # guide.md + note.txt
