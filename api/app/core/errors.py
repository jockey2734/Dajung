"""Unified API error type matching the serving-plan §3 envelope.

serving-plan §3 포맷을 따르는 통합 API 에러 타입.

Every handler raises ``ApiError``; one exception handler in main.py
renders ``{"error": {"code": ..., "message": ...}}``.
모든 핸들러는 ``ApiError``를 던지고, main.py의 예외 핸들러 하나가
``{"error": {"code": ..., "message": ...}}``로 렌더링한다.
"""

from __future__ import annotations


class ApiError(Exception):
    """HTTP error carrying a stable machine code and a human message.

    안정적인 기계용 코드와 사람용 메시지를 담는 HTTP 에러.
    """

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
