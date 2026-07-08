"""Session history routes over in-memory SQLite.

인메모리 SQLite 위의 세션 이력 라우트 테스트.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api.app.core.security import create_access_token, hash_password
from api.app.db.models import ChatSession, Message, User
from api.tests.conftest import ApiHarness


async def _seed_user(
    factory: async_sessionmaker[AsyncSession], email: str = "staff@test.local"
) -> tuple[User, dict[str, str]]:
    async with factory() as session:
        user = User(
            email=email,
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


async def _seed_session(
    factory: async_sessionmaker[AsyncSession],
    user: User,
    title: str,
    n_messages: int = 2,
    minutes_ago: int = 0,
) -> ChatSession:
    when = datetime.now(UTC) - timedelta(minutes=minutes_ago)
    async with factory() as session:
        chat = ChatSession(
            user_id=user.id,
            title=title,
            status="active",
            message_count=n_messages,
            last_message_at=when,
            meta={},
        )
        session.add(chat)
        await session.flush()
        for i in range(n_messages):
            session.add(
                Message(
                    session_id=chat.id,
                    user_id=user.id if i % 2 == 0 else None,
                    role="user" if i % 2 == 0 else "assistant",
                    content=f"메시지 {i}",
                    sequence_no=i + 1,
                    meta={"route": "knowledge_query"} if i % 2 else {},
                )
            )
        await session.commit()
        await session.refresh(chat)
    return chat


async def test_list_orders_by_recent(api_harness: ApiHarness) -> None:
    client, factory, _ = api_harness
    user, headers = await _seed_user(factory)
    await _seed_session(factory, user, "오래된 대화", minutes_ago=60)
    await _seed_session(factory, user, "최신 대화", minutes_ago=1)

    resp = await client.get("/sessions", headers=headers)
    assert resp.status_code == 200
    titles = [s["title"] for s in resp.json()["sessions"]]
    assert titles == ["최신 대화", "오래된 대화"]


async def test_detail_returns_messages_in_order(api_harness: ApiHarness) -> None:
    client, factory, _ = api_harness
    user, headers = await _seed_user(factory)
    chat = await _seed_session(factory, user, "상세", n_messages=3)

    resp = await client.get(f"/sessions/{chat.id}", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert [m["content"] for m in body["messages"]] == ["메시지 0", "메시지 1", "메시지 2"]
    assert body["messages"][1]["metadata"]["route"] == "knowledge_query"


async def test_foreign_session_404_not_403(api_harness: ApiHarness) -> None:
    # Existence must not be revealed (serving-plan §9, 2026-07-08).
    # 존재를 노출하면 안 된다 (serving-plan §9, 2026-07-08).
    client, factory, _ = api_harness
    owner_user, _ = await _seed_user(factory, "a@test.local")
    _, other_headers = await _seed_user(factory, "b@test.local")
    chat = await _seed_session(factory, owner_user, "남의 대화")

    resp = await client.get(f"/sessions/{chat.id}", headers=other_headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


async def test_missing_session_404(api_harness: ApiHarness) -> None:
    client, factory, _ = api_harness
    _, headers = await _seed_user(factory)
    resp = await client.get(f"/sessions/{uuid.uuid4()}", headers=headers)
    assert resp.status_code == 404


async def test_soft_delete_hides_from_list(api_harness: ApiHarness) -> None:
    client, factory, _ = api_harness
    user, headers = await _seed_user(factory)
    chat = await _seed_session(factory, user, "지울 대화")

    resp = await client.delete(f"/sessions/{chat.id}", headers=headers)
    assert resp.status_code == 204
    resp = await client.get("/sessions", headers=headers)
    assert resp.json()["sessions"] == []
    # Detail of a deleted session behaves like a missing one.
    # 삭제된 세션 상세는 없는 세션과 동일하게 동작한다.
    resp = await client.get(f"/sessions/{chat.id}", headers=headers)
    assert resp.status_code == 404


async def test_requires_auth(api_harness: ApiHarness) -> None:
    client, *_ = api_harness
    assert (await client.get("/sessions")).status_code == 401
