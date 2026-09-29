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

# CSV `대분류/소분류` leaf → (doc_type, restricted, sensitivity) — ~/Data_prep.md §F-3
# (two-level scheme, 2026-09-14; the CSV no longer carries the old flat names).
# 2026-07-07 policy: executives-only tool — rosters/chat logs are OPEN.
# Only past incidents are withheld, and those never enter the index (ADR-013).
# sensitivity=high stays on PII rows for the future log-masking policy.
# CSV `대분류/소분류` 잎 → (doc_type, restricted, sensitivity) — ~/Data_prep.md §F-3
# (2단계 체계, 2026-09-14 — CSV에 옛 평면 이름은 더 이상 없다).
# 2026-07-07 정책: 운영진 전용 도구 — 명단·채팅기록 공개. 차단은 사건사고뿐이며
# 그건 인덱스에 아예 안 들어간다(ADR-013). sensitivity=high는 로그 마스킹용 유지.
CATEGORY_MAP: dict[str, tuple[str, bool, str]] = {
    # 교류 leaves are all admin_doc so the handover route finds them — §F-7 files that
    # material under handover knowledge docs (webapp-spec S31 correction 3).
    # 교류 잎은 전부 admin_doc — 인수인계 경로에서 잡혀야 한다. §F-7이 이 자료를
    # 인수인계 지식 문서로 보낸다 (webapp-spec S31 정정 3).
    "지식/세미나-동양차": ("tea_knowledge", False, "low"),
    "지식/세미나-서양차": ("tea_knowledge", False, "low"),
    "지식/세미나-커피": ("coffee_knowledge", False, "low"),
    "지식/다도-다례": ("tea_knowledge", False, "low"),
    "지식/구매처": ("coffee_knowledge", False, "low"),
    "지식/기구-용품": ("equipment", False, "low"),
    "운영/회의록": ("minutes", False, "low"),
    "운영/인수인계": ("handover", False, "medium"),
    "운영/OT-오리엔테이션": ("handover", False, "medium"),
    "운영/운영노하우": ("handover", False, "medium"),
    "운영/회칙": ("operation_rule", False, "low"),
    "운영/동방-규칙": ("operation_rule", False, "low"),
    "운영/활동계획-일정": ("misc", False, "low"),
    "운영/활동보고": ("misc", False, "low"),
    "운영/체크리스트": ("checklist", False, "low"),
    "행정/재등록": ("admin_doc", False, "low"),
    "행정/지원금-보조금": ("admin_doc", False, "low"),
    "행정/동연-대외제출": ("admin_doc", False, "low"),
    "행정/가이드-공지": ("admin_doc", False, "low"),
    "행정/시설-출입": ("admin_doc", False, "low"),
    "재정/예산안": ("budget", False, "low"),
    "재정/장부-결산": ("budget", False, "low"),
    "재정/영수증-증빙": ("budget", False, "low"),
    "홍보/부스": ("misc", False, "low"),
    "홍보/온라인-에타": ("misc", False, "low"),
    "홍보/브랜딩-로고": ("misc", False, "low"),
    "교류/연합-차동연": ("admin_doc", False, "low"),
    "교류/주점-공동행사": ("admin_doc", False, "low"),
    "교류/제휴-제안": ("admin_doc", False, "low"),
    "교류/홈커밍-OB": ("admin_doc", False, "low"),
    "회원/명단-명부": ("misc", False, "high"),
    "회원/신청서-응답": ("misc", False, "high"),
    "회원/회비": ("misc", False, "high"),
    "기록/활동사진": ("misc", False, "low"),
    "기록/채팅기록": ("misc", False, "high"),
}

# `대분류` fallback for a leaf the map doesn't know yet (Data_prep.md §F-8 item 2).
# Member and record groups default to high sensitivity — the conservative side.
# 맵에 아직 없는 잎을 위한 `대분류` 폴백 (Data_prep.md §F-8 항목 2).
# 회원·기록 대분류는 보수적으로 sensitivity=high가 기본이다.
_PARENT_FALLBACK: dict[str, tuple[str, bool, str]] = {
    "지식": ("tea_knowledge", False, "low"),
    "운영": ("misc", False, "low"),
    "행정": ("admin_doc", False, "low"),
    "재정": ("budget", False, "low"),
    "홍보": ("misc", False, "low"),
    "교류": ("admin_doc", False, "low"),
    "회원": ("misc", False, "high"),
    "기록": ("misc", False, "high"),
}
_DEFAULT_META: tuple[str, bool, str] = ("misc", False, "low")

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

_SEM_LABEL = re.compile(r"^20\d{2}-[12]$")
_SEM_FULL = re.compile(r"20(\d{2})-([12])")
_SEM_SHORT = re.compile(r"(?<!\d)(2[3-6])-([12])(?!\d)")
_SEM_DOT = re.compile(r"(?<!\d)(2[3-6])\.(0[1-9]|1[0-2])")


@dataclass
class CsvRow:
    category: str
    folder: str
    modified: str
    semester: str = ""


def category_meta(category: str) -> tuple[str, bool, str]:
    """Map a CSV category to (doc_type, restricted, sensitivity): leaf, then 대분류.

    CSV 카테고리를 (doc_type, restricted, sensitivity)로 매핑한다: 잎 → 대분류 순.
    """
    if category in CATEGORY_MAP:
        return CATEGORY_MAP[category]
    parent = category.split("/", 1)[0]
    return _PARENT_FALLBACK.get(parent, _DEFAULT_META)


def csv_key(relative_path: str) -> str:
    """Normalize a data-root-relative path to the CSV index key (forward slashes).

    data 루트 기준 상대경로를 CSV 인덱스 키(슬래시 구분)로 정규화한다.
    """
    return relative_path.replace("\\", "/").removeprefix("./")


def load_csv_index(csv_path: Path) -> dict[str, CsvRow]:
    """Load the file-inventory CSV keyed by its `상대경로` column.

    파일 목록 CSV를 `상대경로` 열 키로 로드한다.
    Filenames are not unique across the archive once it grows, so the path under
    `data/` is the only safe key (Data_prep.md §F-8 item 1).
    아카이브가 커지면 파일명은 유일하지 않으므로 `data/` 아래 경로만이 안전한 키다
    (Data_prep.md §F-8 항목 1).
    """
    import polars as pl

    if not csv_path.exists():
        return {}
    df = pl.read_csv(csv_path)
    index: dict[str, CsvRow] = {}
    for row in df.iter_rows(named=True):
        relative = str(row.get("상대경로") or row["파일명"])
        index[csv_key(relative)] = CsvRow(
            category=str(row.get("카테고리") or ""),
            folder=str(row.get("폴더") or ""),
            modified=str(row.get("수정일시") or ""),
            semester=str(row.get("학기") or ""),
        )
    return index


def csv_row_for(index: dict[str, CsvRow], path: Path, data_dir: Path) -> CsvRow | None:
    """Find a file's CSV row by its path under data_dir; None when outside it.

    data_dir 아래 경로로 파일의 CSV 행을 찾는다. data_dir 밖이면 None.
    """
    try:
        relative = path.resolve().relative_to(data_dir.resolve())
    except ValueError:
        return None
    return index.get(csv_key(relative.as_posix()))


def infer_semester(filename: str, csv_semester: str = "") -> str | None:
    """Return 'YYYY-N': the CSV `학기` column first, then filename patterns.

    'YYYY-N'을 반환한다: CSV `학기` 열 우선, 다음 파일명 패턴.
    The modified timestamp is never used — the whole archive was copied to the
    server in 2026, so mtime says nothing about the material (Data_prep.md §F-4).
    수정일시는 쓰지 않는다 — 아카이브 전체가 2026년에 서버로 복사돼 mtime은
    자료 시점과 무관하다 (Data_prep.md §F-4).
    """
    if _SEM_LABEL.match(csv_semester):
        return csv_semester
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
    doc_type, restricted, sensitivity = category_meta(category)

    payload: dict[str, Any] = {
        "doc_id": doc_id_for(str(path)),
        "source_file": path.name,
        "doc_type": doc_type,
        "category": category,
        "role": "general",
        "semester": infer_semester(path.name, csv_row.semester if csv_row else ""),
        "topic": None,
        "sensitivity": sensitivity,
        "requires_hitl": False,
        "chunk_index": chunk.chunk_index,
        "total_chunks": chunk.total_chunks,
        "locator": chunk.locator,
        # Never the CSV 수정일시: it is the 2026 server-copy time, and build_context
        # would show every archive chunk to the model as modified in 2026 (S31-4).
        # CSV 수정일시는 넣지 않는다: 2026 서버 복사 시각이라 build_context가 모든
        # 아카이브 청크를 2026년 수정본처럼 모델에 보여준다 (S31 정정 4).
        "last_modified": "",
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
