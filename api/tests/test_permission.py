"""Permission regression suite — CI gate (CLAUDE.md §5.2, Dajung.md §9).

권한 회귀 테스트 — CI 게이트 (CLAUDE.md §5.2, Dajung.md §9).
Red here must block any merge to main.
여기가 빨간불이면 main 머지를 차단해야 한다.
"""

from __future__ import annotations

from typing import Any

from qdrant_client.models import FieldCondition, MatchAny, MatchValue

from api.app.graph.nodes.permission import permission_node
from api.app.graph.state import State
from api.app.rag.qdrant_store import build_permission_filter

# ── layer 1: Qdrant filter ──────────────────────────────────────────────────


def test_owner_filter_is_none(fake_user_owner: dict[str, str]) -> None:
    # Owner must bypass filtering entirely.
    # owner는 필터링을 완전히 우회해야 한다.
    assert build_permission_filter(fake_user_owner) is None


def test_staff_filter_shape(fake_user_staff: dict[str, str]) -> None:
    flt = build_permission_filter(fake_user_staff)
    assert flt is not None
    assert flt.must is None and flt.must_not is None
    should = flt.should
    assert isinstance(should, list) and len(should) == 2

    open_cond, whitelist_cond = should
    assert isinstance(open_cond, FieldCondition)
    assert open_cond.key == "restricted"
    assert isinstance(open_cond.match, MatchValue) and open_cond.match.value is False

    assert isinstance(whitelist_cond, FieldCondition)
    assert whitelist_cond.key == "allowed_users"
    assert isinstance(whitelist_cond.match, MatchAny)
    assert whitelist_cond.match.any == [fake_user_staff["id"]]


def test_missing_role_treated_as_non_owner() -> None:
    # A malformed user dict must fail closed, never open.
    # 잘못된 user dict는 항상 닫는 쪽으로 처리되어야 한다.
    flt = build_permission_filter({"id": "user-x", "email": "x@test.local"})
    assert flt is not None


# ── layer 2: in-process node ────────────────────────────────────────────────


def _run_node(user: dict[str, str], candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    state: State = {"query": "q", "user": user, "candidates": candidates}
    return permission_node(state)["candidates"]


def test_staff_cannot_see_restricted(
    fake_user_staff: dict[str, str], fake_chunks: list[dict[str, Any]]
) -> None:
    result = _run_node(fake_user_staff, fake_chunks)
    for c in result:
        payload = c["payload"]
        assert (not payload["restricted"]) or fake_user_staff["id"] in payload["allowed_users"]
    # chunks 2 (restricted, empty whitelist) and 4 (whitelisted to someone else)
    # must be gone; whitelisted chunk 3 must survive.
    # 2번(제한·화이트리스트 없음)·4번(타인 화이트리스트)은 제거, 3번(본인 화이트리스트)은 생존.
    doc_ids = {c["payload"]["doc_id"] for c in result}
    assert doc_ids == {"doc-0", "doc-1", "doc-3", "doc-5"}


def test_whitelisted_staff_sees_allowed_chunk(
    fake_user_staff: dict[str, str], fake_chunks: list[dict[str, Any]]
) -> None:
    result = _run_node(fake_user_staff, fake_chunks)
    assert any(c["payload"]["doc_id"] == "doc-3" for c in result)


def test_owner_can_access_restricted(
    fake_user_owner: dict[str, str], fake_chunks: list[dict[str, Any]]
) -> None:
    result = _run_node(fake_user_owner, fake_chunks)
    assert len(result) == len(fake_chunks)


def test_empty_candidates_safe(fake_user_staff: dict[str, str]) -> None:
    assert _run_node(fake_user_staff, []) == []


def test_other_staff_not_leaked_by_whitelist(fake_chunks: list[dict[str, Any]]) -> None:
    # A different staff user must not inherit user-staff-1's whitelist entry.
    # 다른 staff가 user-staff-1의 화이트리스트를 물려받으면 안 된다.
    other = {"id": "user-staff-2", "email": "other@test.local", "role": "staff"}
    doc_ids = {c["payload"]["doc_id"] for c in _run_node(other, fake_chunks)}
    assert doc_ids == {"doc-0", "doc-1", "doc-5"}
