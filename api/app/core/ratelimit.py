"""Shared slowapi limiter — per-IP budgets on auth endpoints.

공유 slowapi 리미터 — 인증 엔드포인트의 IP당 예산.
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from api.app.core.config import settings

limiter = Limiter(key_func=get_remote_address)


def ip_limit() -> str:
    """Read the limit per request so tests can shrink it via settings.

    요청마다 설정을 읽어 테스트가 settings로 한도를 줄일 수 있게 한다.
    """
    return settings.rate_limit_ip
