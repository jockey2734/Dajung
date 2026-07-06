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


def rerank(query: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Precision-sort candidate dicts; return top rerank_top_k with scores.

    후보 dict를 정밀 정렬해 상위 rerank_top_k를 점수와 함께 반환한다.
    Candidates are `{"payload": {...}, "score": float}` dicts (graph contract).
    후보는 `{"payload": {...}, "score": float}` dict다 (그래프 계약).
    """
    if not candidates:
        return []
    pairs = [
        [query, f"{c['payload']['context_header']}\n{c['payload']['text']}"] for c in candidates
    ]
    scores = _get_reranker().compute_score(pairs, normalize=True)
    if isinstance(scores, float):
        # Single pair returns a bare float.
        # 쌍이 하나면 float 하나가 온다.
        scores = [scores]
    ranked = sorted(
        (
            {"payload": c["payload"], "rerank_score": float(s)}
            for c, s in zip(candidates, scores, strict=True)
        ),
        key=lambda item: float(item["rerank_score"]),
        reverse=True,
    )
    return ranked[: settings.rerank_top_k]
