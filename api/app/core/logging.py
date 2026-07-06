"""Structlog setup for CLI and (later) API processes.

CLI와 (이후) API 프로세스용 structlog 설정.
"""

from __future__ import annotations

import logging

import structlog


def configure_logging(level: int = logging.INFO) -> None:
    """Configure structlog with a console renderer.

    콘솔 렌더러로 structlog를 설정한다.
    """
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="%H:%M:%S"),
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a named bound logger.

    이름이 부여된 로거를 반환한다.
    """
    return structlog.get_logger(name)  # type: ignore[no-any-return]
