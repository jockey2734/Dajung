"""Second-layer permission cut on retrieved candidates (Dajung.md §8.17).

검색 후보에 대한 2겹째 권한 차단 (Dajung.md §8.17).
Layer 1 is the Qdrant filter (rag/qdrant_store.py); this node re-checks in
process so a bug or bypass in layer 1 still cannot leak restricted chunks
to the LLM.
1겹은 Qdrant 필터(rag/qdrant_store.py)다. 이 노드는 프로세스 안에서
재검사해, 1겹의 버그·우회가 있어도 restricted 청크가 LLM에 새지 않게 한다.
"""

from __future__ import annotations

from typing import Any

from api.app.graph.state import State


def permission_node(state: State) -> dict[str, list[dict[str, Any]]]:
    """Drop candidates the user must not see.

    사용자가 볼 수 없는 후보를 제거한다.
    """
    assert "candidates" in state and "user" in state
    user = state["user"]
    if user.get("role") == "owner":
        return {"candidates": state["candidates"]}
    allowed = [
        c
        for c in state["candidates"]
        if not c["payload"]["restricted"] or user["id"] in c["payload"]["allowed_users"]
    ]
    return {"candidates": allowed}
