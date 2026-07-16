"""Clarify node — fixed re-ask for unclear routes (Dajung.md §8.15.6).

clarify 노드 — unclear 라우트용 고정 되묻기 (Dajung.md §8.15.6).
No LLM call: deterministic, free, and test-stable.
LLM 호출 없음: 결정적이고 무료이며 테스트가 흔들리지 않는다.
"""

from __future__ import annotations

from typing import Any

from api.app.graph.history import prepend_history
from api.app.graph.state import State

CLARIFY_MESSAGE = (
    "질문의 의도를 정확히 파악하지 못했습니다. 다음 중 어느 쪽에 가까운가요?\n"
    "1) 동아리 지식·규칙·자료 내용 질문  2) 직책 인수인계 관련 질문\n"
    '조금 더 구체적으로 다시 질문해 주세요. (예: "25-1 예산안에서 다과 지출 얼마였어?")'
)


def clarify_node(state: State) -> dict[str, Any]:
    """Return the fixed clarification prompt as the answer.

    고정 되묻기 문구를 답변으로 반환한다.
    """
    assert "query" in state
    answer = prepend_history(CLARIFY_MESSAGE, state.get("history", []))
    return {"answer": answer, "model_used": "none", "citations": []}
