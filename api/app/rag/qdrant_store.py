"""Qdrant access layer — permission filter first (Dajung.md §8.8).

Qdrant 접근 계층 — 권한 필터 우선 구현 (Dajung.md §8.8).
Collection management and hybrid search land with feat/cx-cli-ingest /
feat/cx-cli-rag; this module starts with the security-critical filter so
every retrieval path is forced to build its filter here.
컬렉션 관리·하이브리드 검색은 feat/cx-cli-ingest / feat/cx-cli-rag에서
추가된다. 보안 핵심인 필터를 먼저 두어 모든 검색 경로가 반드시 여기서
필터를 만들게 한다.
"""

from __future__ import annotations

from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue


def build_permission_filter(user: dict[str, str]) -> Filter | None:
    """Build the retrieval-stage permission filter for a user.

    사용자에 대한 검색 단계 권한 필터를 만든다.

    Rules (CLAUDE.md §5.2 — cut at retrieval, before the LLM sees anything):
    - owner: no filter at all — full visibility, including restricted docs.
    - everyone else: a chunk is visible iff it is not restricted OR the
      user id is explicitly whitelisted in allowed_users.
    규칙 (CLAUDE.md §5.2 — LLM에 닿기 전 검색 단계에서 차단):
    - owner: 필터 없음 — restricted 포함 전부 열람.
    - 그 외: restricted가 아니거나 allowed_users에 명시된 청크만 보인다.
    """
    if user.get("role") == "owner":
        # Owner bypass — omitting this breaks test_owner_can_access_restricted.
        # owner 우회 — 빠뜨리면 test_owner_can_access_restricted가 깨진다.
        return None
    return Filter(
        should=[
            FieldCondition(key="restricted", match=MatchValue(value=False)),
            FieldCondition(key="allowed_users", match=MatchAny(any=[user["id"]])),
        ]
    )
