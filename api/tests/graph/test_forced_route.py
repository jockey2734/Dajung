"""Forced-route bypass in the router node (Dajung.md §8.2).

라우터 노드의 강제 라우트 우회 (Dajung.md §8.2).
"""

from __future__ import annotations

import pytest

from api.app.graph.nodes import router as router_mod
from api.app.graph.state import Route, State


async def test_preset_route_skips_ollama(monkeypatch: pytest.MonkeyPatch) -> None:
    async def boom(*args: object, **kwargs: object) -> str:
        raise AssertionError("Ollama must not be called when route is forced")

    monkeypatch.setattr(router_mod._client, "chat", boom)
    state: State = {
        "query": "아무 질문",
        "user": {"id": "u", "email": "e", "role": "staff"},
        "route": Route.HANDOVER_QUERY,
    }
    out = await router_mod.router_node(state)
    assert out["route"] == Route.HANDOVER_QUERY
    assert out["retries"] == 0
