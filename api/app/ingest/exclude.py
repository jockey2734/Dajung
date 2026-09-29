"""Ingest exclusion rules (Dajung.md §8.6, ADR-013).

인덱싱 제외 규칙 (Dajung.md §8.6, ADR-013).
Pure function, no I/O — the pipeline passes the CSV category when known.
순수 함수, I/O 없음 — CSV 카테고리는 파이프라인이 알 때 넘겨준다.
"""

from __future__ import annotations

from pathlib import Path

# Image formats are excluded in MVP1; Vision captions are a PoC decision.
# 이미지 포맷은 MVP1에서 제외. Vision 캡션은 PoC 결정 사항.
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".jfif", ".gif"}
# Two-level CSV leaves (Data_prep.md §F-3); the old flat names no longer occur.
# CSV 2단계 잎 (Data_prep.md §F-3). 옛 평면 이름은 더 이상 나오지 않는다.
_IMAGE_CATEGORIES = {"홍보/브랜딩-로고", "기록/활동사진"}


def is_excluded(path: Path, csv_category: str | None = None) -> tuple[bool, str]:
    """Decide whether a file must be skipped by ingest.

    ingest가 이 파일을 건너뛰어야 하는지 판정한다.
    Returns (excluded, reason); reason is one of
    "incident" | "tempfile" | "image" | "trash" | "hidden" | "".
    (제외 여부, 사유)를 반환한다.
    """
    # Rule 1 — incident originals never enter the index (ADR-013).
    # 규칙 1 — 사건사고 원문은 인덱스에 절대 넣지 않는다 (ADR-013).
    if any(part == "사건사고" for part in path.parts):
        return True, "incident"

    # Rule 2 — editor lock/temp files.
    # 규칙 2 — 편집기 잠금·임시 파일.
    if path.name.startswith("~$") or path.suffix.lower() == ".tmp":
        return True, "tempfile"

    # Rule 3 — image extensions (MVP1 policy).
    # 규칙 3 — 이미지 확장자 (MVP1 정책).
    if path.suffix.lower() in _IMAGE_EXTS:
        return True, "image"

    # Rule 4 — CSV says it is branding/photo material.
    # 규칙 4 — CSV 분류가 브랜딩·사진 자료.
    if csv_category in _IMAGE_CATEGORIES:
        return True, "image"

    # Rule 5 — recoverable deletions never re-enter the index.
    # 규칙 5 — 복구용 삭제 파일은 인덱스에 다시 들어가지 않는다.
    if ".trash" in path.parts:
        return True, "trash"

    # Rule 6 — hidden files.
    # 규칙 6 — 숨김 파일.
    if path.name.startswith("."):
        return True, "hidden"

    return False, ""
