"""Message feedback routes over synthetic in-memory data.

합성 인메모리 데이터 기반 메시지 피드백 라우트 테스트.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api.app.core.security import create_access_token, hash_password
from api.app.db.models import ChatSession, Feedback, Message, User
from api.tests.conftest import ApiHarness


@dataclass(frozen=True)
class SeededConversation:
    user: User
    headers: dict[str, str]
    chat: ChatSession
    user_message: Message
    assistant_message: Message


async def _seed_conversation(
    factory: async_sessionmaker[AsyncSession], email: str = "staff@test.local"
) -> SeededConversation:
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
        await session.flush()

        chat = ChatSession(
            user_id=user.id,
            title="피드백 테스트",
            status="active",
            message_count=2,
            meta={},
        )
        session.add(chat)
        await session.flush()

        user_message = Message(
            session_id=chat.id,
            user_id=user.id,
            role="user",
            content="질문",
            sequence_no=1,
            meta={},
        )
        assistant_message = Message(
            session_id=chat.id,
            user_id=None,
            role="assistant",
            content="답변",
            sequence_no=2,
            meta={"route": "knowledge_query"},
        )
        session.add_all([user_message, assistant_message])
        await session.commit()

    token = create_access_token(user.id, user.email, user.role)
    return SeededConversation(
        user=user,
        headers={"Authorization": f"Bearer {token}"},
        chat=chat,
        user_message=user_message,
        assistant_message=assistant_message,
    )


async def test_put_creates_and_restores_feedback(api_harness: ApiHarness) -> None:
    client, factory, _ = api_harness
    seeded = await _seed_conversation(factory)

    response = await client.put(
        f"/messages/{seeded.assistant_message.id}/feedback",
        headers=seeded.headers,
        json={"rating": 1, "comment": "도움이 됐어요"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "message_id": str(seeded.assistant_message.id),
        "rating": 1,
        "comment": "도움이 됐어요",
    }

    detail = await client.get(f"/sessions/{seeded.chat.id}", headers=seeded.headers)
    assert detail.status_code == 200
    assert [message["my_feedback"] for message in detail.json()["messages"]] == [None, 1]


async def test_put_updates_existing_feedback(api_harness: ApiHarness) -> None:
    client, factory, _ = api_harness
    seeded = await _seed_conversation(factory)
    url = f"/messages/{seeded.assistant_message.id}/feedback"

    assert (
        await client.put(url, headers=seeded.headers, json={"rating": 1, "comment": "처음"})
    ).status_code == 200
    response = await client.put(
        url,
        headers=seeded.headers,
        json={"rating": -1, "comment": "다시 평가"},
    )

    assert response.status_code == 200
    assert response.json()["rating"] == -1
    assert response.json()["comment"] == "다시 평가"
    async with factory() as session:
        count = (
            await session.execute(
                select(func.count()).select_from(Feedback).where(Feedback.user_id == seeded.user.id)
            )
        ).scalar_one()
    assert count == 1


async def test_put_rejects_invalid_rating(api_harness: ApiHarness) -> None:
    client, factory, _ = api_harness
    seeded = await _seed_conversation(factory)

    response = await client.put(
        f"/messages/{seeded.assistant_message.id}/feedback",
        headers=seeded.headers,
        json={"rating": 0},
    )

    assert response.status_code == 422


async def test_feedback_hides_foreign_message(api_harness: ApiHarness) -> None:
    client, factory, _ = api_harness
    owner = await _seed_conversation(factory, "owner@test.local")
    other = await _seed_conversation(factory, "other@test.local")
    url = f"/messages/{owner.assistant_message.id}/feedback"

    put_response = await client.put(url, headers=other.headers, json={"rating": 1})
    delete_response = await client.delete(url, headers=other.headers)

    assert put_response.status_code == 404
    assert put_response.json()["error"]["code"] == "not_found"
    assert delete_response.status_code == 404


async def test_feedback_rejects_user_message(api_harness: ApiHarness) -> None:
    client, factory, _ = api_harness
    seeded = await _seed_conversation(factory)
    url = f"/messages/{seeded.user_message.id}/feedback"

    put_response = await client.put(url, headers=seeded.headers, json={"rating": 1})
    delete_response = await client.delete(url, headers=seeded.headers)

    assert put_response.status_code == 422
    assert put_response.json()["error"]["code"] == "feedback_not_allowed"
    assert delete_response.status_code == 422


async def test_delete_feedback_clears_session_detail(api_harness: ApiHarness) -> None:
    client, factory, _ = api_harness
    seeded = await _seed_conversation(factory)
    url = f"/messages/{seeded.assistant_message.id}/feedback"
    await client.put(url, headers=seeded.headers, json={"rating": -1})

    response = await client.delete(url, headers=seeded.headers)

    assert response.status_code == 204
    detail = await client.get(f"/sessions/{seeded.chat.id}", headers=seeded.headers)
    assert [message["my_feedback"] for message in detail.json()["messages"]] == [None, None]
    assert (await client.delete(url, headers=seeded.headers)).status_code == 404


async def test_feedback_missing_message_is_404(api_harness: ApiHarness) -> None:
    client, factory, _ = api_harness
    seeded = await _seed_conversation(factory)
    missing_url = f"/messages/{uuid.uuid4()}/feedback"

    assert (
        await client.put(missing_url, headers=seeded.headers, json={"rating": 1})
    ).status_code == 404
    assert (await client.delete(missing_url, headers=seeded.headers)).status_code == 404


async def test_feedback_requires_authentication(api_harness: ApiHarness) -> None:
    client, factory, _ = api_harness
    seeded = await _seed_conversation(factory)
    url = f"/messages/{seeded.assistant_message.id}/feedback"

    assert (await client.put(url, json={"rating": 1})).status_code == 401
    assert (await client.delete(url)).status_code == 401
