"""Cite node — map [n] markers to sources, scrub invalid ones (Dajung.md §8.15.7).

cite 노드 — [n] 마커를 출처에 매핑하고 무효 마커는 제거 (Dajung.md §8.15.7).
"""

from __future__ import annotations

import re
from typing import Any

from api.app.graph.state import State
from api.app.rag.answer import citations_for

_MARKER = re.compile(r"\[(\d+)\]")


def strip_invalid_markers(answer: str, n_sources: int) -> str:
    """Remove [n] markers that point outside the provided sources.

    제공된 자료 범위를 벗어나는 [n] 마커를 제거한다.
    """

    def _sub(m: re.Match[str]) -> str:
        n = int(m.group(1))
        return m.group(0) if 1 <= n <= n_sources else ""

    return _MARKER.sub(_sub, answer)


def cite_node(state: State) -> dict[str, Any]:
    """Build the citations list and clean the answer text.

    인용 목록을 만들고 답변 텍스트를 정리한다.
    """
    assert "answer" in state
    reranked = state.get("reranked", [])
    answer = strip_invalid_markers(state["answer"], len(reranked))
    return {"answer": answer, "citations": citations_for(answer, reranked)}
