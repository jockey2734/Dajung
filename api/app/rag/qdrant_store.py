"""Qdrant access layer (Dajung.md §8.8 + §8.10).

Qdrant 접근 계층 (Dajung.md §8.8 + §8.10).
Permission filter, collection lifecycle, upsert, hybrid search, stats.
권한 필터, 컬렉션 생성, 업서트, 하이브리드 검색, 통계.
"""

from __future__ import annotations

import uuid
from functools import lru_cache
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    Fusion,
    FusionQuery,
    MatchAny,
    MatchValue,
    Modifier,
    PayloadSchemaType,
    PointStruct,
    Prefetch,
    ScoredPoint,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)

from api.app.core.config import settings

_UPSERT_BATCH = 64

# Payload fields that get an index for filtering (Dajung.md §8.8).
# 필터링용 인덱스를 만드는 payload 필드 (Dajung.md §8.8).
_PAYLOAD_INDEXES: dict[str, PayloadSchemaType] = {
    "doc_type": PayloadSchemaType.KEYWORD,
    "semester": PayloadSchemaType.KEYWORD,
    "restricted": PayloadSchemaType.BOOL,
    "category": PayloadSchemaType.KEYWORD,
    "doc_id": PayloadSchemaType.KEYWORD,
}


@lru_cache(maxsize=1)
def get_client() -> QdrantClient:
    return QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)


def build_permission_filter(user: dict[str, str]) -> Filter | None:
    """Build the retrieval-stage permission filter for a user.

    사용자에 대한 검색 단계 권한 필터를 만든다.

    Rules (CLAUDE.md §5.2 — cut at retrieval, before the LLM sees anything):
    - owner: no filter at all — full visibility, including restricted docs.
    - everyone else: a chunk is visible iff it is not restricted OR the
      user id is explicitly whitelisted in allowed_users.
    규칙 (CLAUDE.md §5.2 — LLM에 닿기 전 검색 단계에서 차단):
    - owner: 필터 없음 — restricted 포함 전부 열람.
    - 그 외: restricted가 아니거나 allowed_users에 명시된 청크만 보인다.
    """
    if user.get("role") == "owner":
        # Owner bypass — omitting this breaks test_owner_can_access_restricted.
        # owner 우회 — 빠뜨리면 test_owner_can_access_restricted가 깨진다.
        return None
    return Filter(
        should=[
            FieldCondition(key="restricted", match=MatchValue(value=False)),
            FieldCondition(key="allowed_users", match=MatchAny(any=[user["id"]])),
        ]
    )


def ensure_collection() -> None:
    """Create the hybrid collection and payload indexes if missing.

    하이브리드 컬렉션·payload 인덱스가 없으면 만든다.
    """
    client = get_client()
    if not client.collection_exists(settings.collection):
        client.create_collection(
            collection_name=settings.collection,
            vectors_config={"dense": VectorParams(size=1024, distance=Distance.COSINE)},
            sparse_vectors_config={"sparse": SparseVectorParams(modifier=Modifier.IDF)},
        )
        for field, schema in _PAYLOAD_INDEXES.items():
            client.create_payload_index(
                collection_name=settings.collection, field_name=field, field_schema=schema
            )


def delete_doc(doc_id: str) -> None:
    """Remove every chunk of a document before re-upserting.

    재업서트 전에 문서의 모든 청크를 지운다.
    """
    get_client().delete(
        collection_name=settings.collection,
        points_selector=Filter(must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]),
    )


def upsert_chunks(
    payloads: list[dict[str, Any]],
    dense_vectors: list[list[float]],
    sparse_vectors: list[dict[int, float]],
) -> int:
    """Upsert chunk points in batches; returns point count.

    청크 포인트를 배치 업서트한다. 포인트 수를 반환.
    """
    assert len(payloads) == len(dense_vectors) == len(sparse_vectors)
    client = get_client()
    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector={
                "dense": dense,
                "sparse": SparseVector(indices=list(sparse.keys()), values=list(sparse.values())),
            },
            payload=payload,
        )
        for payload, dense, sparse in zip(payloads, dense_vectors, sparse_vectors, strict=True)
    ]
    for start in range(0, len(points), _UPSERT_BATCH):
        client.upsert(
            collection_name=settings.collection, points=points[start : start + _UPSERT_BATCH]
        )
    return len(points)


def hybrid_search(
    dense_vec: list[float],
    sparse_vec: dict[int, float],
    flt: Filter | None,
    limit: int,
) -> list[ScoredPoint]:
    """Dense + sparse prefetch fused with RRF (Dajung.md §8.10).

    dense + sparse prefetch를 RRF로 융합한다 (Dajung.md §8.10).
    """
    sparse = SparseVector(indices=list(sparse_vec.keys()), values=list(sparse_vec.values()))
    return (
        get_client()
        .query_points(
            collection_name=settings.collection,
            prefetch=[
                Prefetch(query=dense_vec, using="dense", limit=limit, filter=flt),
                Prefetch(query=sparse, using="sparse", limit=limit, filter=flt),
            ],
            query=FusionQuery(fusion=Fusion.RRF),
            limit=limit,
            with_payload=True,
        )
        .points
    )


def collection_stats() -> str:
    """Human-readable collection stats for `dajung stats`.

    `dajung stats`용 사람이 읽는 컬렉션 통계.
    """
    client = get_client()
    if not client.collection_exists(settings.collection):
        return f"컬렉션 '{settings.collection}' 없음 — 먼저 `dajung ingest`를 실행하세요."
    total = client.count(collection_name=settings.collection).count
    lines = [f"collection: {settings.collection}", f"chunks: {total}"]
    facet = client.facet(collection_name=settings.collection, key="doc_type")
    for hit in facet.hits:
        lines.append(f"  {hit.value}: {hit.count}")
    return "\n".join(lines)
