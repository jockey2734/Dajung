"""Clarify node cases.

clarify 노드 케이스.
"""

from __future__ import annotations

from api.app.graph.nodes.clarify import CLARIFY_MESSAGE, clarify_node
from api.app.graph.state import State


def test_clarify_returns_fixed_message() -> None:
    state: State = {"query": "음"}
    out = clarify_node(state)
    assert out["answer"] == CLARIFY_MESSAGE
    assert out["model_used"] == "none"
    assert out["citations"] == []


def test_clarify_message_offers_both_routes() -> None:
    # The re-ask must steer the user toward one of the two MVP1 routes.
    # 되묻기는 MVP1 두 라우트 중 하나로 유도해야 한다.
    assert "지식" in CLARIFY_MESSAGE and "인수인계" in CLARIFY_MESSAGE
