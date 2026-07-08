"""Per-email login lockout — 5 failures in 5 min locks for 1 h (SECURITY.md §3).

이메일 단위 로그인 잠금 — 5분 내 5회 실패 시 1시간 잠금 (SECURITY.md §3).

State is process-local: a restart clears it. Acceptable at club scale
(single api container, ≤8 users) and avoids a DB table for hot-path writes.
상태는 프로세스 로컬 — 재시작하면 초기화된다. 단일 api 컨테이너·8명 이하
규모에서 허용 가능하며, 핫패스 쓰기용 DB 테이블을 피한다.
"""

from __future__ import annotations

import time


class LoginLockout:
    """Sliding-window failure counter with a hard lock period.

    슬라이딩 윈도우 실패 카운터 + 고정 잠금 시간.
    """

    def __init__(self, max_fails: int, window_s: int, lock_s: int) -> None:
        self.max_fails = max_fails
        self.window_s = window_s
        self.lock_s = lock_s
        self._fails: dict[str, list[float]] = {}
        self._locked_until: dict[str, float] = {}

    def is_locked(self, email: str) -> bool:
        until = self._locked_until.get(email)
        if until is None:
            return False
        if time.monotonic() >= until:
            # Lock expired — drop all state for the email.
            # 잠금 만료 — 해당 이메일 상태 전부 제거.
            del self._locked_until[email]
            self._fails.pop(email, None)
            return False
        return True

    def record_failure(self, email: str) -> None:
        now = time.monotonic()
        window_start = now - self.window_s
        recent = [t for t in self._fails.get(email, []) if t > window_start]
        recent.append(now)
        self._fails[email] = recent
        if len(recent) >= self.max_fails:
            self._locked_until[email] = now + self.lock_s

    def clear(self, email: str) -> None:
        """Successful login wipes the failure history.

        로그인 성공 시 실패 이력을 지운다.
        """
        self._fails.pop(email, None)
        self._locked_until.pop(email, None)
