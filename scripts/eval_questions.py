"""MVP1 eval — 20 real questions through the graph (Dajung.md §8.18-a).

MVP1 평가 — 실질문 20개를 그래프로 실행 (Dajung.md §8.18-a).
Needs the live stack (Qdrant, Ollama, Anthropic key). Run:
라이브 스택 필요 (Qdrant, Ollama, Anthropic 키). 실행:

    uv run python scripts/eval_questions.py
"""

from __future__ import annotations

import time
from pathlib import Path

import polars as pl

from api.app.graph.graph import get_app
from api.app.graph.state import Route, State

# Draft question set — 운하님 확인 후 확정 (지식 12 · 인수인계 6 · 모호 2).
# Draft set — to be finalized with Unha (12 knowledge · 6 handover · 2 vague).
QUESTIONS: list[tuple[str, Route | None]] = [
    ("개완으로 차 우리는 법 알려줘", Route.KNOWLEDGE_QUERY),
    ("핸드드립 내릴 때 물 온도 몇 도가 좋아?", Route.KNOWLEDGE_QUERY),
    ("동아리방 사용 규칙이 뭐야?", Route.KNOWLEDGE_QUERY),
    ("홍보부스 운영할 때 준비물 체크리스트 어디 있어?", Route.KNOWLEDGE_QUERY),
    ("25-1 예산안에서 다과 지출 얼마였어?", Route.KNOWLEDGE_QUERY),
    ("작년 가을 세미나에서 어떤 차 다뤘어?", Route.KNOWLEDGE_QUERY),
    ("카페탐방 가이드라인 요약해줘", Route.KNOWLEDGE_QUERY),
    ("재등록 서류에 뭐가 들어가야 해?", Route.KNOWLEDGE_QUERY),
    ("동방투어 인원 배치 어떻게 했었지?", Route.KNOWLEDGE_QUERY),
    ("행사지원금 신청 절차 알려줘", Route.KNOWLEDGE_QUERY),
    ("회의록 양식 어떻게 생겼어?", Route.KNOWLEDGE_QUERY),
    ("지난 회의에서 결정된 사항 정리해줘", Route.KNOWLEDGE_QUERY),
    ("신임 회장이 학기 초에 해야 할 일 알려줘", Route.HANDOVER_QUERY),
    ("총무 처음 맡았는데 뭐부터 챙겨야 해?", Route.HANDOVER_QUERY),
    ("회장직 물려받으면서 확인할 문서 목록 줘", Route.HANDOVER_QUERY),
    ("세미나 담당 인수인계 받을 때 주의할 점?", Route.HANDOVER_QUERY),
    ("다음 운영진한테 넘겨줄 자료 뭐뭐 있어?", Route.HANDOVER_QUERY),
    ("신임 운영진 온보딩 어떻게 진행했었어?", Route.HANDOVER_QUERY),
    ("그거 있잖아 그거", None),  # unclear 기대 · expect unclear
    ("음 뭐부터 물어봐야 하지", None),
]

_USER = {"id": "cli-local", "email": "local", "role": "owner"}
_REPORT = Path("docs/eval_report.md")


def main() -> None:
    import asyncio
    import uuid

    app = get_app()
    rows: list[dict[str, object]] = []
    for question, expected in QUESTIONS:
        state: State = {"query": question, "user": dict(_USER)}
        started = time.monotonic()
        try:
            final = asyncio.run(
                app.ainvoke(state, {"configurable": {"thread_id": str(uuid.uuid4())}})
            )
            route = str(final.get("route", ""))
            ok = expected is None or route == str(expected)
            rows.append(
                {
                    "question": question,
                    "route": route,
                    "route_ok": ok,
                    "n_citations": len(final.get("citations", [])),
                    "model": final.get("model_used", ""),
                    "latency_ms": int((time.monotonic() - started) * 1000),
                }
            )
        except Exception as exc:
            rows.append(
                {
                    "question": question,
                    "route": f"ERROR: {type(exc).__name__}",
                    "route_ok": False,
                    "n_citations": 0,
                    "model": "",
                    "latency_ms": int((time.monotonic() - started) * 1000),
                }
            )

    df = pl.DataFrame(rows)
    print(df)

    route_ok = int(df["route_ok"].sum())
    cited = int((df["n_citations"] > 0).sum())
    verdict = [
        f"route 정확: {route_ok}/20 (기준 ≥18)",
        f"인용 있는 답변: {cited}/20 (기준 ≥15)",
        "판정: "
        + ("PASS" if route_ok >= 18 and cited >= 15 else "FAIL — 라우터 few-shot 보강 검토"),
    ]
    print("\n".join(verdict))

    _REPORT.parent.mkdir(exist_ok=True)
    with _REPORT.open("a", encoding="utf-8") as f:
        f.write(f"\n## eval {time.strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write("\n".join(verdict) + "\n\n")
        f.write(str(df) + "\n")


if __name__ == "__main__":
    main()
