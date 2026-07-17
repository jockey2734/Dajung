"""Chat SSE endpoint over in-memory SQLite with the graph mocked.

그래프를 모킹한 인메모리 SQLite 위의 채팅 SSE 테스트.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api.app.core.config import settings
from api.app.core.security import create_access_token, hash_password
from api.app.db.models import ChatSession, Message, ModelRun, RetrievalEvent, User, UserMemory
from api.app.routes import chat as chat_mod
from api.tests.conftest import ApiHarness


@pytest.fixture(autouse=True)
def _qdrant_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chat_mod, "_qdrant_ready", lambda: True)


@pytest.fixture(autouse=True)
def _no_title_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_title(question: str, answer: str) -> str:
        return ""

    monkeypatch.setattr(chat_mod, "_haiku_title", fake_title)


async def _seed_user(factory: async_sessionmaker[AsyncSession]) -> tuple[User, dict[str, str]]:
    async with factory() as session:
        user = User(
            email="staff@test.local",
            password_hash=hash_password("pw12345678"),
            name="스태프",
            role="staff",
            status="active",
            profile={},
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    token = create_access_token(user.id, user.email, user.role)
    return user, {"Authorization": f"Bearer {token}"}


class FakeGraph:
    def __init__(self, *updates: dict[str, Any]) -> None:
        self._updates = updates

    async def astream(
        self, state: Any, config: Any, stream_mode: str
    ) -> AsyncIterator[dict[str, Any]]:
        assert stream_mode == "updates"
        for u in self._updates:
            yield u


def _override_graph(app: Any, *updates: dict[str, Any]) -> None:
    app.dependency_overrides[chat_mod.get_graph] = lambda: FakeGraph(*updates)


def _capture_graph_states(app: Any, *updates: dict[str, Any]) -> list[dict[str, Any]]:
    states: list[dict[str, Any]] = []

    class CapturingGraph(FakeGraph):
        async def astream(
            self, state: Any, config: Any, stream_mode: str
        ) -> AsyncIterator[dict[str, Any]]:
            states.append(dict(state))
            async for update in super().astream(state, config, stream_mode):
                yield update

    app.dependency_overrides[chat_mod.get_graph] = lambda: CapturingGraph(*(updates or _HAPPY))
    return states


async def _seed_chat_session(
    factory: async_sessionmaker[AsyncSession],
    user: User,
    messages: list[dict[str, Any]],
) -> uuid.UUID:
    async with factory() as session:
        chat = ChatSession(user_id=user.id, title="합성 대화", status="active", meta={})
        session.add(chat)
        await session.flush()
        for sequence_no, values in enumerate(messages, start=1):
            role = str(values["role"])
            session.add(
                Message(
                    session_id=chat.id,
                    user_id=user.id if role == "user" else None,
                    role=role,
                    content=str(values["content"]),
                    sequence_no=sequence_no,
                    status=str(values.get("status", "completed")),
                    deleted_at=values.get("deleted_at"),
                )
            )
        chat.message_count = len(messages)
        await session.commit()
        return chat.id


_HAPPY = (
    {"router": {"route": "knowledge_query", "retries": 0}},
    {"rerank": {"reranked": [], "route_after": "generate"}},
    {
        "generate": {
            "answer": "개완은 이렇게 씁니다. 연락처는 010-1234-5678 [1].",
            "model_used": "claude-haiku-4-5",
        }
    },
    {
        "cite": {
            "answer": "개완은 이렇게 씁니다. 연락처는 010-1234-5678 [1].",
            "citations": [{"kind": "doc", "marker": 1}],
        }
    },
)


def _events(sse_text: str) -> list[tuple[str, dict[str, Any]]]:
    """Parse an SSE body into (event, data) pairs.

    SSE 본문을 (event, data) 쌍으로 파싱한다.
    """
    out: list[tuple[str, dict[str, Any]]] = []
    event = ""
    for line in sse_text.splitlines():
        if line.startswith("event: "):
            event = line[7:]
        elif line.startswith("data: "):
            out.append((event, json.loads(line[6:])))
    return out


async def test_event_sequence_and_persistence(
    api_harness: ApiHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, factory, app = api_harness
    _, headers = await _seed_user(factory)
    _override_graph(app, *_HAPPY)

    resp = await client.post("/chat/stream", json={"query": "개완 사용법"}, headers=headers)
    assert resp.status_code == 200
    events = _events(resp.text)
    kinds = [e for e, _ in events]
    # webapp-plan §7 order: session → status* → route → token* → citations → done
    assert kinds[0] == "session" and kinds[-1] == "done"
    assert kinds.index("route") < kinds.index("token") < kinds.index("citations")
    done = next(d for e, d in events if e == "done")
    assert done["remaining"] == settings.daily_chat_limit - 1
    assert "offer" not in done
    streamed_answer = "".join(data["text"] for event, data in events if event == "token")
    assert "010-1234-5678" not in streamed_answer
    assert "[전화]" in streamed_answer
    assert {"stage": "routing", "label": chat_mod._STATUS_LABELS["routing"]} == next(
        d for e, d in events if e == "status"
    )

    session_id = uuid.UUID(events[0][1]["session_id"])
    async with factory() as s:
        chat = await s.get(ChatSession, session_id)
        assert chat is not None
        assert chat.message_count == 2
        rows = (await s.execute(select(Message).order_by(Message.sequence_no))).scalars().all()
        runs = (await s.execute(select(ModelRun))).scalars().all()
        retrievals = (await s.execute(select(RetrievalEvent))).scalars().all()
    assert [r.role for r in rows] == ["user", "assistant"]
    assert "010-1234-5678" not in rows[1].content
    assert "[전화]" in rows[1].content
    assert rows[1].meta["route"] == "knowledge_query"
    assert rows[1].meta["citations"] == [{"kind": "doc", "marker": 1}]
    assert rows[1].status == "completed"
    assert len(runs) == 1 and runs[0].message_id == rows[1].id
    assert len(retrievals) == 1 and retrievals[0].message_id == rows[1].id


async def test_pii_masked_at_write(
    api_harness: ApiHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, factory, app = api_harness
    _, headers = await _seed_user(factory)
    _override_graph(app, *_HAPPY)

    await client.post("/chat/stream", json={"query": "010-1234-5678로 연락 줘"}, headers=headers)
    async with factory() as s:
        row = (await s.execute(select(Message).where(Message.role == "user"))).scalars().one()
    assert "010-1234-5678" not in row.content
    assert "[전화]" in row.content


async def test_continue_existing_session(
    api_harness: ApiHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, factory, app = api_harness
    _, headers = await _seed_user(factory)
    _override_graph(app, *_HAPPY)

    first = await client.post("/chat/stream", json={"query": "첫 질문"}, headers=headers)
    session_id = _events(first.text)[0][1]["session_id"]

    second = await client.post(
        "/chat/stream", json={"query": "이어서", "session_id": session_id}, headers=headers
    )
    events = _events(second.text)
    # No `session` event when continuing (webapp-plan §7: 신규일 때만).
    # 이어가기에는 session 이벤트가 없다 (webapp-plan §7: 신규일 때만).
    assert events[0][0] != "session"
    async with factory() as s:
        chat = await s.get(ChatSession, uuid.UUID(session_id))
        assert chat is not None and chat.message_count == 4


async def test_user_memory_added_to_graph_state(
    api_harness: ApiHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, factory, app = api_harness
    user, headers = await _seed_user(factory)
    async with factory() as s:
        s.add(UserMemory(user_id=user.id, content="- 인수인계 문서를 자주 확인함"))
        await s.commit()
    seen_states: list[dict[str, Any]] = []

    class CapturingGraph:
        async def astream(
            self, state: Any, config: Any, stream_mode: str
        ) -> AsyncIterator[dict[str, Any]]:
            seen_states.append(dict(state))
            yield {"router": {"route": "knowledge_query", "retries": 0}}
            yield {"generate": {"answer": "답변", "model_used": "claude-haiku-4-5"}}
            yield {"cite": {"answer": "답변", "citations": []}}

    app.dependency_overrides[chat_mod.get_graph] = lambda: CapturingGraph()
    resp = await client.post("/chat/stream", json={"query": "질문"}, headers=headers)

    assert resp.status_code == 200
    assert seen_states[0]["user_memory"] == "- 인수인계 문서를 자주 확인함"


async def test_history_window_is_chronological_and_excludes_current_turn(
    api_harness: ApiHarness,
) -> None:
    client, factory, app = api_harness
    user, headers = await _seed_user(factory)
    session_id = await _seed_chat_session(
        factory,
        user,
        [
            {
                "role": "user" if index % 2 else "assistant",
                "content": f"history-{index:02d}",
            }
            for index in range(1, 12)
        ],
    )
    seen_states = _capture_graph_states(app)

    response = await client.post(
        "/chat/stream",
        json={"query": "current-turn", "session_id": str(session_id)},
        headers=headers,
    )

    assert response.status_code == 200
    assert [item["content"] for item in seen_states[0]["history"]] == [
        f"history-{index:02d}" for index in range(2, 12)
    ]
    assert all(item["content"] != "current-turn" for item in seen_states[0]["history"])


async def test_history_excludes_other_session_deleted_and_incomplete_assistant(
    api_harness: ApiHarness,
) -> None:
    client, factory, app = api_harness
    user, headers = await _seed_user(factory)
    session_id = await _seed_chat_session(
        factory,
        user,
        [
            {"role": "user", "content": "keep-user-any-status", "status": "failed"},
            {"role": "assistant", "content": "drop-failed", "status": "failed"},
            {"role": "assistant", "content": "keep-completed"},
            {
                "role": "user",
                "content": "drop-deleted",
                "deleted_at": datetime.now(UTC),
            },
            {"role": "assistant", "content": "drop-streaming", "status": "streaming"},
        ],
    )
    await _seed_chat_session(factory, user, [{"role": "user", "content": "drop-other"}])
    seen_states = _capture_graph_states(app)

    response = await client.post(
        "/chat/stream",
        json={"query": "follow-up", "session_id": str(session_id)},
        headers=headers,
    )

    assert response.status_code == 200
    assert seen_states[0]["history"] == [
        {"role": "user", "content": "keep-user-any-status"},
        {"role": "assistant", "content": "keep-completed"},
    ]


async def test_new_session_omits_empty_history_key(api_harness: ApiHarness) -> None:
    client, factory, app = api_harness
    _, headers = await _seed_user(factory)
    seen_states = _capture_graph_states(app)

    response = await client.post("/chat/stream", json={"query": "first-turn"}, headers=headers)

    assert response.status_code == 200
    assert "history" not in seen_states[0]


async def test_done_remaining_reflects_current_turn(
    api_harness: ApiHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, factory, app = api_harness
    user, headers = await _seed_user(factory)
    _override_graph(app, *_HAPPY)
    monkeypatch.setattr(settings, "daily_chat_limit", 3)
    async with factory() as s:
        chat = ChatSession(user_id=user.id, title="이전", status="active", meta={})
        s.add(chat)
        await s.flush()
        s.add(
            Message(
                session_id=chat.id,
                user_id=user.id,
                role="user",
                content="이전 질문",
                sequence_no=1,
            )
        )
        await s.commit()

    resp = await client.post("/chat/stream", json={"query": "남은 횟수?"}, headers=headers)
    assert resp.status_code == 200
    done = next(data for event, data in _events(resp.text) if event == "done")
    assert done["remaining"] == 1


@pytest.mark.parametrize("mode", ["rag", "web", "plain"])
async def test_daily_limit_blocks_all_modes(
    api_harness: ApiHarness, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    client, factory, app = api_harness
    user, headers = await _seed_user(factory)
    _override_graph(app, *_HAPPY)
    monkeypatch.setattr(settings, "daily_chat_limit", 1)
    async with factory() as s:
        chat = ChatSession(user_id=user.id, title="이전", status="active", meta={})
        s.add(chat)
        await s.flush()
        s.add(
            Message(
                session_id=chat.id,
                user_id=user.id,
                role="user",
                content="이전 질문",
                sequence_no=1,
            )
        )
        await s.commit()

    resp = await client.post("/chat/stream", json={"query": "한도?", "mode": mode}, headers=headers)
    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "daily_limit"


async def test_foreign_session_404(
    api_harness: ApiHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, factory, app = api_harness
    _, headers = await _seed_user(factory)
    _override_graph(app, *_HAPPY)
    resp = await client.post(
        "/chat/stream", json={"query": "q", "session_id": str(uuid.uuid4())}, headers=headers
    )
    assert resp.status_code == 404


async def test_qdrant_down_503(api_harness: ApiHarness, monkeypatch: pytest.MonkeyPatch) -> None:
    client, factory, app = api_harness
    _, headers = await _seed_user(factory)
    _override_graph(app, *_HAPPY)
    monkeypatch.setattr(chat_mod, "_qdrant_ready", lambda: False)
    resp = await client.post("/chat/stream", json={"query": "q"}, headers=headers)
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "qdrant_down"


async def test_offer_web_streams_and_persists_optional_offer(
    api_harness: ApiHarness,
) -> None:
    client, factory, app = api_harness
    _, headers = await _seed_user(factory)
    offer_message = "문서 검색에 실패했습니다. 웹 검색을 시도해보시겠습니까?"
    _override_graph(
        app,
        {"router": {"route": "knowledge_query", "retries": 0}},
        {"rerank": {"reranked": [], "route_after": "offer_web"}},
        {
            "offer_web": {
                "answer": offer_message,
                "model_used": "none",
                "offer": "web_search",
                "citations": [],
            }
        },
    )

    response = await client.post("/chat/stream", json={"query": "없는 문서"}, headers=headers)

    assert response.status_code == 200
    events = _events(response.text)
    assert "".join(data["text"] for event, data in events if event == "token") == offer_message
    done = next(data for event, data in events if event == "done")
    assert done["offer"] == "web_search"
    async with factory() as session:
        assistant = (
            (await session.execute(select(Message).where(Message.role == "assistant")))
            .scalars()
            .one()
        )
    assert assistant.meta["offer"] == "web_search"
    assert assistant.meta["citations"] == []


async def test_web_mode_bypasses_qdrant_and_emits_web_citations(
    api_harness: ApiHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, factory, app = api_harness
    _, headers = await _seed_user(factory)
    monkeypatch.setattr(chat_mod, "_qdrant_ready", lambda: False)
    citations = [{"kind": "web", "title": "공식", "url": "https://example.test"}]
    seen_states = _capture_graph_states(
        app,
        {
            "web_generate": {
                "answer": "(웹 검색 결과 — 동아리 내부 자료 아님)\n공개 답변",
                "model_used": "claude-sonnet-5",
                "citations": citations,
            }
        },
    )

    response = await client.post(
        "/chat/stream",
        json={"query": "원 질문", "mode": "web", "route": "handover"},
        headers=headers,
    )

    assert response.status_code == 200
    assert seen_states[0]["mode"] == "web"
    assert "route" not in seen_states[0]
    events = _events(response.text)
    assert next(data for event, data in events if event == "citations") == {"citations": citations}
    answer = "".join(data["text"] for event, data in events if event == "token")
    assert answer.startswith("(웹 검색 결과 — 동아리 내부 자료 아님)\n")
    async with factory() as session:
        retrievals = (await session.execute(select(RetrievalEvent))).scalars().all()
        assistant = (
            (await session.execute(select(Message).where(Message.role == "assistant")))
            .scalars()
            .one()
        )
    assert retrievals == []
    assert assistant.meta["citations"] == citations


async def test_plain_mode_bypasses_qdrant_without_citations(
    api_harness: ApiHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, factory, app = api_harness
    _, headers = await _seed_user(factory)
    monkeypatch.setattr(chat_mod, "_qdrant_ready", lambda: False)
    seen_states = _capture_graph_states(
        app,
        {
            "plain_generate": {
                "answer": "(동아리 자료·웹 근거 없음 — 일반 지식 답변)\n일반 답변",
                "model_used": "claude-sonnet-5",
                "citations": [],
            }
        },
    )

    response = await client.post(
        "/chat/stream", json={"query": "원 질문", "mode": "plain"}, headers=headers
    )

    assert response.status_code == 200
    assert seen_states[0]["mode"] == "plain"
    events = _events(response.text)
    assert all(event != "citations" for event, _ in events)
    answer = "".join(data["text"] for event, data in events if event == "token")
    assert answer.startswith("(동아리 자료·웹 근거 없음 — 일반 지식 답변)\n")
    async with factory() as session:
        retrievals = (await session.execute(select(RetrievalEvent))).scalars().all()
    assert retrievals == []


async def test_graph_error_logs_failed_turn(
    api_harness: ApiHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, factory, app = api_harness
    _, headers = await _seed_user(factory)

    class ExplodingGraph:
        async def astream(
            self, state: Any, config: Any, stream_mode: str
        ) -> AsyncIterator[dict[str, Any]]:
            raise RuntimeError("anthropic exploded")
            yield {}

    app.dependency_overrides[chat_mod.get_graph] = lambda: ExplodingGraph()
    resp = await client.post("/chat/stream", json={"query": "q"}, headers=headers)
    events = _events(resp.text)
    assert events[-1][0] == "error"
    assert events[-1][1]["error"]["code"] == "llm_down"
    async with factory() as s:
        failed = (
            (await s.execute(select(Message).where(Message.status == "failed"))).scalars().all()
        )
    assert len(failed) == 1 and failed[0].error_code == "llm_down"


async def test_requires_auth(api_harness: ApiHarness) -> None:
    client, *_ = api_harness
    assert (await client.post("/chat/stream", json={"query": "q"})).status_code == 401
