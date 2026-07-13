"""Knowledge-document storage, ingest, and recoverable deletion.

지식 문서 저장·인덱싱·복구 가능한 삭제.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from api.app.core.config import settings
from api.app.core.logging import get_logger
from api.app.ingest.metadata import doc_id_for
from api.app.ingest.pipeline import (
    flush_manifest,
    load_manifest,
    run_ingest_file,
)
from api.app.rag.qdrant_store import delete_doc

log = get_logger(__name__)

ALLOWED_DOCUMENT_EXTENSIONS = {".md", ".txt", ".csv", ".pdf", ".docx", ".xlsx", ".pptx"}
MAX_DOCUMENT_FILENAME_CHARS = 255


class DocumentValidationError(Exception):
    """Raised when a folder, filename, extension, or size is unsafe.

    폴더·파일명·확장자·크기가 안전하지 않을 때 발생한다.
    """


class DocumentConflictError(Exception):
    """Raised when an upload would replace an existing source file.

    업로드가 기존 원본을 덮어쓰려 할 때 발생한다.
    """


class DocumentNotFoundError(Exception):
    """Raised when a manifest cannot resolve the requested document.

    매니페스트에서 요청 문서를 찾을 수 없을 때 발생한다.
    """


class DocumentInfrastructureError(Exception):
    """Raised when index deletion fails after a recoverable file move.

    복구 가능한 파일 이동 후 인덱스 삭제가 실패할 때 발생한다.
    """


def available_document_folders() -> set[str]:
    """Return safe immediate child directories under the data root.

    data 루트 바로 아래의 안전한 디렉토리를 반환한다.
    """
    root = settings.data_dir
    if not root.exists():
        return set()
    return {
        path.name
        for path in root.iterdir()
        if path.is_dir()
        and not path.is_symlink()
        and not path.name.startswith(".")
        and path.name != "사건사고"
    }


def validate_document_target(folder: str, filename: str) -> Path:
    """Validate user-controlled path components and return a safe target.

    사용자 입력 경로 요소를 검증하고 안전한 대상 경로를 반환한다.
    """
    if folder == "사건사고" or folder not in available_document_folders():
        raise DocumentValidationError("선택할 수 없는 문서 폴더입니다.")
    if (
        not filename
        or filename.startswith(".")
        or ".." in filename
        or "/" in filename
        or "\\" in filename
        or len(filename.encode("utf-8")) > MAX_DOCUMENT_FILENAME_CHARS
    ):
        raise DocumentValidationError("안전하지 않은 파일명입니다.")
    if Path(filename).suffix.lower() not in ALLOWED_DOCUMENT_EXTENSIONS:
        raise DocumentValidationError("지원하지 않는 파일 형식입니다.")

    target = settings.data_dir / folder / filename
    if target.parent.resolve() != (settings.data_dir / folder).resolve():
        raise DocumentValidationError("안전하지 않은 파일 경로입니다.")
    if target.exists():
        raise DocumentConflictError(filename)
    return target


def store_document(folder: str, filename: str, data: bytes) -> Path:
    """Write a validated document without replacing existing data.

    검증한 문서를 기존 데이터를 교체하지 않고 저장한다.
    """
    target = validate_document_target(folder, filename)
    try:
        with target.open("xb") as output:
            output.write(data)
    except FileExistsError as exc:
        raise DocumentConflictError(filename) from exc
    return target


def ingest_document(path: Path) -> None:
    """Run one background ingest and record errors without leaking content.

    단일 백그라운드 인덱싱을 실행하고 본문 노출 없이 오류를 기록한다.
    """
    try:
        report = run_ingest_file(path)
    except Exception as exc:  # noqa: BLE001 — background work must not crash the response
        log.error("document ingest failed", file=path.name, error=type(exc).__name__)
        return
    if report.errors:
        log.error("document ingest failed", file=path.name, errors=len(report.errors))


def _manifest_source(doc_id: str, manifest: dict[str, str]) -> tuple[str, Path]:
    matches = [key for key in manifest if doc_id_for(key) == doc_id]
    if len(matches) != 1:
        raise DocumentNotFoundError(doc_id)
    key = matches[0]
    source = Path(key)
    resolved = source.resolve()
    try:
        resolved.relative_to(settings.data_dir.resolve())
    except ValueError as exc:
        raise DocumentNotFoundError(doc_id) from exc
    if not resolved.is_file():
        raise DocumentNotFoundError(doc_id)
    return key, resolved


def delete_document(doc_id: str) -> None:
    """Move a source to trash and remove manifest and vector state atomically enough to recover.

    원본을 휴지통으로 옮기고 매니페스트·벡터 상태를 실패 시 복구 가능하게 제거한다.
    """
    manifest = load_manifest()
    key, source = _manifest_source(doc_id, manifest)
    stored_hash = manifest[key]
    trash_dir = settings.data_dir.resolve() / ".trash"
    trash_dir.mkdir(parents=True, exist_ok=True)
    trash_path = trash_dir / f"{doc_id[:8]}-{source.name}"
    if trash_path.exists():
        trash_path = trash_dir / f"{uuid.uuid4().hex[:8]}-{source.name}"

    source.replace(trash_path)
    try:
        manifest.pop(key)
        flush_manifest(manifest)
        delete_doc(doc_id)
    except Exception as exc:
        if trash_path.exists():
            trash_path.replace(source)
        manifest[key] = stored_hash
        flush_manifest(manifest)
        raise DocumentInfrastructureError(doc_id) from exc
