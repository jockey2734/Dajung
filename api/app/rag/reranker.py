"""bge-reranker-v2-m3 wrapper — CPU only (Dajung.md §8.11).

bge-reranker-v2-m3 래퍼 — CPU 전용 (Dajung.md §8.11).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from api.app.core.config import settings

if TYPE_CHECKING:
    from FlagEmbedding import FlagReranker

_RERANKER: FlagReranker | None = None


def _get_reranker() -> FlagReranker:
    """Load the reranker once, CPU only — the GPU belongs to Ollama.

    리랭커를 1회만 로드, CPU 전용 — GPU는 Ollama 몫이다.
    """
    from FlagEmbedding import FlagReranker

    global _RERANKER
    if _RERANKER is None:
        _RERANKER = FlagReranker(settings.rerank_model, use_fp16=False)
    return _RERANKER


def rerank(query: str, points: list[Any]) -> list[dict[str, Any]]:
    """Precision-sort candidates; return top rerank_top_k with scores.

    후보를 정밀 정렬해 상위 rerank_top_k를 점수와 함께 반환한다.
    """
    if not points:
        return []
    pairs = [
        [query, f"{p.payload['context_header']}\n{p.payload['text']}"]
        for p in points
        if p.payload is not None
    ]
    scores = _get_reranker().compute_score(pairs, normalize=True)
    if isinstance(scores, float):
        # Single pair returns a bare float.
        # 쌍이 하나면 float 하나가 온다.
        scores = [scores]
    ranked = sorted(
        (
            {"payload": p.payload, "rerank_score": float(s)}
            for p, s in zip(points, scores, strict=True)
        ),
        key=lambda item: item["rerank_score"],
        reverse=True,
    )
    return ranked[: settings.rerank_top_k]
