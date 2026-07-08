"""Rerank node retry decision cases (Dajung.md §9).

리랭크 노드 재시도 결정 케이스 (Dajung.md §9).
"""

from __future__ import annotations

from typing import Any

import pytest

from api.app.graph.nodes import rerank as rerank_mod
from api.app.graph.state import Route, State


def _patch_scores(monkeypatch: pytest.MonkeyPatch, scores: list[float]) -> None:
    def fake_rerank(query: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{"payload": {"i": i}, "rerank_score": s} for i, s in enumerate(scores)]

    monkeypatch.setattr(rerank_mod, "rerank", fake_rerank)


def _state(route: Route, retries: int) -> State:
    return {
        "query": "q",
        "route": route,
        "retries": retries,
        "candidates": [{"payload": {}, "score": 1.0}],
    }


def test_low_score_first_try_retries_same_route(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_scores(monkeypatch, [0.3])
    out = rerank_mod.rerank_node(_state(Route.HANDOVER_QUERY, 0))
    assert out["route_after"] == "retrieve_handover"
    assert out["retries"] == 1


def test_low_score_after_retry_generates(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_scores(monkeypatch, [0.3])
    out = rerank_mod.rerank_node(
        _state(Route.HANDOVER_QUERY, rerank_mod.settings.max_retries)
    )
    assert out["route_after"] == "generate_handover"
    assert "retries" not in out


def test_good_score_goes_straight_to_generate(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_scores(monkeypatch, [0.8, 0.6])
    out = rerank_mod.rerank_node(_state(Route.KNOWLEDGE_QUERY, 0))
    assert out["route_after"] == "generate"


def test_empty_candidates_generate_path(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_scores(monkeypatch, [])
    out = rerank_mod.rerank_node(
        _state(Route.KNOWLEDGE_QUERY, rerank_mod.settings.max_retries)
    )
    # Empty + retries exhausted → generate emits the honest no-source answer.
    # 비었고 재시도 소진 → generate가 정직한 '자료 없음' 답변을 낸다.
    assert out["route_after"] == "generate"
    assert out["reranked"] == []


def test_route_after_rerank_pure_lookup() -> None:
    assert rerank_mod.route_after_rerank({"route_after": "generate"}) == "generate"
