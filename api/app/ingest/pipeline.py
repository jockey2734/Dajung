"""Ingest pipeline: scan → parse → chunk → header → embed → upsert (Dajung.md §8.9).

ingest 파이프라인: 스캔 → 파싱 → 청킹 → 헤더 → 임베딩 → 업서트 (Dajung.md §8.9).
Manifest-based idempotency; per-file errors never abort the run.
매니페스트 기반 멱등성. 파일 단위 오류는 전체 실행을 멈추지 않는다.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from api.app.core.config import settings
from api.app.core.logging import get_logger
from api.app.ingest.chunker import chunk_document
from api.app.ingest.context_header import header_for_chunk, summarize_document
from api.app.ingest.exclude import is_excluded
from api.app.ingest.metadata import (
    CsvRow,
    build_payload,
    csv_row_for,
    doc_id_for,
    infer_semester,
    load_csv_index,
    parse_frontmatter,
)
from api.app.ingest.parsers import ParserError, parse_file

if TYPE_CHECKING:
    from api.app.rag.embedder import Embedder

log = get_logger(__name__)

_EMBEDDER: Embedder | None = None


def _get_embedder() -> Embedder:
    """Load the (heavy) embedder lazily and only once.

    무거운 임베더를 지연·1회만 로드한다.
    """
    from api.app.rag.embedder import Embedder

    global _EMBEDDER
    if _EMBEDDER is None:
        _EMBEDDER = Embedder()
    return _EMBEDDER


@dataclass
class IngestReport:
    scanned: int = 0
    skipped_manifest: int = 0
    excluded: Counter[str] = field(default_factory=Counter)
    upserted_chunks: int = 0
    errors: list[tuple[str, str]] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"scanned: {self.scanned}",
            f"skipped (manifest): {self.skipped_manifest}",
            f"excluded: {dict(self.excluded)}",
            f"upserted chunks: {self.upserted_chunks}",
            f"errors: {len(self.errors)}",
        ]
        lines.extend(f"  {name}: {err}" for name, err in self.errors)
        return "\n".join(lines)


def load_manifest() -> dict[str, str]:
    path = settings.manifest_path
    if path.exists():
        data: dict[str, str] = json.loads(path.read_text(encoding="utf-8"))
        return data
    return {}


def flush_manifest(manifest: dict[str, str]) -> None:
    path = settings.manifest_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")


def run_ingest(target_dir: Path, rebuild: bool = False, dry_run: bool = False) -> IngestReport:
    """Ingest every eligible file under target_dir.

    target_dir 아래 대상 파일을 전부 인덱싱한다.
    dry_run: parse/chunk stats only — no LLM, no embedding, no upsert,
    and the manifest is left untouched.
    dry_run: 파싱·청킹 통계만 — LLM·임베딩·업서트 없음, 매니페스트도 안 건드림.
    """
    paths = sorted(path for path in target_dir.rglob("*") if path.is_file())
    return _run_ingest_paths(paths, rebuild=rebuild, dry_run=dry_run)


def run_ingest_file(path: Path, dry_run: bool = False) -> IngestReport:
    """Ingest one eligible file through the same pipeline as the CLI.

    CLI와 같은 파이프라인으로 대상 파일 하나만 인덱싱한다.
    """
    return _run_ingest_paths([path], rebuild=False, dry_run=dry_run)


def _run_ingest_paths(paths: list[Path], *, rebuild: bool, dry_run: bool) -> IngestReport:
    report = IngestReport()
    csv_index = load_csv_index(settings.csv_path)
    manifest = {} if rebuild else load_manifest()

    if not dry_run:
        from api.app.rag.qdrant_store import ensure_collection

        ensure_collection()

    for path in paths:
        csv_row: CsvRow | None = csv_row_for(csv_index, path, settings.data_dir)
        excluded, reason = is_excluded(path, csv_row.category if csv_row else None)
        if excluded:
            report.excluded[reason] += 1
            continue
        report.scanned += 1

        try:
            raw = path.read_bytes()
            doc_hash = hashlib.sha256(raw).hexdigest()[:16]
            if manifest.get(str(path)) == doc_hash:
                report.skipped_manifest += 1
                continue

            parsed = parse_file(path)

            # Curated markdown carries YAML frontmatter overrides.
            # 큐레이션 마크다운은 YAML frontmatter로 메타를 덮어쓴다.
            frontmatter: dict[str, object] = {}
            if path.suffix.lower() == ".md":
                frontmatter, body = parse_frontmatter(parsed.text)
                parsed.text = body

            chunks = chunk_document(parsed, path.suffix)
            for chunk in chunks:
                chunk.total_chunks = len(chunks)

            if dry_run:
                log.info("dry-run", file=path.name, chunks=len(chunks))
                continue

            category = csv_row.category if csv_row else ""
            semester = infer_semester(path.name, csv_row.semester if csv_row else "")
            doc_summary = summarize_document(parsed.text)

            payloads = []
            texts = []
            for chunk in chunks:
                header = header_for_chunk(
                    chunk,
                    source_file=path.name,
                    category=category,
                    semester=semester,
                    doc_summary=doc_summary,
                )
                payloads.append(
                    build_payload(
                        path,
                        csv_row,
                        chunk,
                        doc_hash,
                        context_header=header,
                        frontmatter=frontmatter,
                    )
                )
                texts.append(f"{header}\n---\n{chunk.text}")

            from api.app.rag.qdrant_store import delete_doc, upsert_chunks

            embedded = _get_embedder().encode(texts)
            delete_doc(doc_id_for(str(path)))
            report.upserted_chunks += upsert_chunks(
                payloads,
                [e.dense for e in embedded],
                [e.sparse for e in embedded],
            )

            manifest[str(path)] = doc_hash
            flush_manifest(manifest)
            log.info("ingested", file=path.name, chunks=len(chunks))

        except ParserError as exc:
            report.errors.append((path.name, f"{type(exc).__name__}: {exc}"))
            log.warning("parse failed", file=path.name, error=str(exc))
        except Exception as exc:
            report.errors.append((path.name, f"{type(exc).__name__}: {exc}"))
            log.error("ingest failed", file=path.name, error=str(exc))

    return report
