"""Payload metadata: CSV mapping, semester inference, frontmatter (Dajung.md §8.5).

payload 메타데이터: CSV 매핑, 학기 추론, frontmatter (Dajung.md §8.5).
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from api.app.ingest.chunker import Chunk

# CSV category → (doc_type, restricted, sensitivity). Table from Dajung.md §8.5.
# CSV 카테고리 → (doc_type, restricted, sensitivity). Dajung.md §8.5 표 그대로.
# 2026-07-07 policy: executives-only tool — rosters/chat logs are OPEN.
# Only past incidents are withheld, and those never enter the index (ADR-013).
# sensitivity=high stays on PII rows for the future log-masking policy.
# 2026-07-07 정책: 운영진 전용 도구 — 명단·채팅기록 공개. 차단은 사건사고뿐이며
# 그건 인덱스에 아예 안 들어간다(ADR-013). sensitivity=high는 로그 마스킹용 유지.
CATEGORY_MAP: dict[str, tuple[str, bool, str]] = {
    "인수인계": ("handover", False, "medium"),
    "회의록": ("minutes", False, "low"),
    "예산안": ("budget", False, "low"),
    "세미나-교육자료": ("tea_knowledge", False, "low"),
    "재등록-행정서류": ("admin_doc", False, "low"),
    "지원금-보조금 신청": ("admin_doc", False, "low"),
    "행정서류-가이드": ("admin_doc", False, "low"),
    "제휴-제안서": ("admin_doc", False, "low"),
    "회원명단-신청서": ("misc", False, "high"),
    "채팅기록": ("misc", False, "high"),
    "카페탐방": ("misc", False, "low"),
    "동방투어": ("misc", False, "low"),
    "홍보부스": ("misc", False, "low"),
    "활동기록-일정": ("misc", False, "low"),
    "소모임-네트워킹": ("misc", False, "low"),
}

# Curated-knowledge folder → doc_type (Dajung.md §10.2).
# 큐레이션 지식 폴더 → doc_type (Dajung.md §10.2).
_FRONTMATTER_DOC_TYPES = {
    "handover",
    "tea_knowledge",
    "coffee_knowledge",
    "equipment",
    "checklist",
    "operation_rule",
    "minutes",
    "budget",
    "admin_doc",
    "misc",
}

_SEM_FULL = re.compile(r"20(\d{2})-([12])")
_SEM_SHORT = re.compile(r"(?<!\d)(2[3-6])-([12])(?!\d)")
_SEM_DOT = re.compile(r"(?<!\d)(2[3-6])\.(0[1-9]|1[0-2])")
_SEM_ISO = re.compile(r"(20\d{2})-(0[1-9]|1[0-2])-")


@dataclass
class CsvRow:
    category: str
    folder: str
    modified: str


def load_csv_index(csv_path: Path) -> dict[str, CsvRow]:
    """Load the file-inventory CSV keyed by filename.

    파일 목록 CSV를 파일명 키로 로드한다.
    """
    import polars as pl

    if not csv_path.exists():
        return {}
    df = pl.read_csv(csv_path)
    index: dict[str, CsvRow] = {}
    for row in df.iter_rows(named=True):
        index[str(row["파일명"])] = CsvRow(
            category=str(row.get("카테고리") or ""),
            folder=str(row.get("폴더") or ""),
            modified=str(row.get("수정일시") or ""),
        )
    return index


def infer_semester(filename: str, modified: str) -> str | None:
    """Infer 'YYYY-N' semester from filename patterns, then modified date.

    파일명 패턴 → 수정일시 순으로 'YYYY-N' 학기를 추론한다.
    """
    m = _SEM_FULL.search(filename)
    if m:
        return f"20{m.group(1)}-{m.group(2)}"
    m = _SEM_SHORT.search(filename)
    if m:
        return f"20{m.group(1)}-{m.group(2)}"
    m = _SEM_DOT.search(filename)
    if m:
        month = int(m.group(2))
        return f"20{m.group(1)}-{1 if month <= 6 else 2}"
    m = _SEM_ISO.search(modified)
    if m:
        month = int(m.group(2))
        return f"{m.group(1)}-{1 if month <= 6 else 2}"
    return None


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split YAML frontmatter from a curated markdown body.

    큐레이션 마크다운에서 YAML frontmatter와 본문을 분리한다.
    """
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return {}, text
    if not isinstance(meta, dict):
        return {}, text
    return meta, parts[2].lstrip("\n")


def doc_id_for(source_path: str) -> str:
    """Deterministic doc id — same path always maps to the same uuid.

    결정적 doc id — 같은 경로는 항상 같은 uuid.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, source_path))


def build_payload(
    path: Path,
    csv_row: CsvRow | None,
    chunk: Chunk,
    doc_hash: str,
    context_header: str = "",
    frontmatter: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble the Qdrant payload for one chunk (system-design §4.3).

    청크 하나의 Qdrant payload를 조립한다 (system-design §4.3).
    """
    category = csv_row.category if csv_row else ""
    modified = csv_row.modified if csv_row else ""
    doc_type, restricted, sensitivity = CATEGORY_MAP.get(category, ("misc", False, "low"))

    # Seminar decks about coffee count as coffee knowledge.
    # 커피 관련 세미나 자료는 coffee_knowledge로 분류한다.
    if category == "세미나-교육자료" and "커피" in path.name:
        doc_type = "coffee_knowledge"

    payload: dict[str, Any] = {
        "doc_id": doc_id_for(str(path)),
        "source_file": path.name,
        "doc_type": doc_type,
        "category": category,
        "role": "general",
        "semester": infer_semester(path.name, modified),
        "topic": None,
        "sensitivity": sensitivity,
        "requires_hitl": False,
        "chunk_index": chunk.chunk_index,
        "total_chunks": chunk.total_chunks,
        "locator": chunk.locator,
        "last_modified": modified,
        "restricted": restricted,
        "allowed_users": [],
        "tags": [],
        "text": chunk.text,
        "context_header": context_header,
        "doc_hash": doc_hash,
    }

    # Curated markdown overrides via frontmatter (Dajung.md §8.5).
    # 큐레이션 마크다운은 frontmatter로 덮어쓴다 (Dajung.md §8.5).
    if frontmatter:
        for key in ("role", "semester", "topic", "sensitivity", "requires_hitl"):
            if key in frontmatter:
                payload[key] = frontmatter[key]
        fm_type = frontmatter.get("doc_type")
        if fm_type in _FRONTMATTER_DOC_TYPES:
            payload["doc_type"] = fm_type
        if "restricted" in frontmatter:
            payload["restricted"] = bool(frontmatter["restricted"])

    return payload
