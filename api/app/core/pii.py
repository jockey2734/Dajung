"""Write-time PII masking for message content (SECURITY.md §8).

메시지 본문 기록 시점 PII 마스킹 (SECURITY.md §8).
Structured contact/student patterns only. Names and club roles are retained
because they are the expected operating context.
연락처·학번 같은 구조화 패턴만 마스킹한다. 이름과 동아리 직책은
업무 맥락상 보존한다.
"""

from __future__ import annotations

import re

# Patterns are the S1 contract in docs/webapp-spec.md.
# 패턴은 docs/webapp-spec.md S1 계약 그대로다.
_PHONE = re.compile(r"01[016789]-?\d{3,4}-?\d{4}")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_STUDENT_ID = re.compile(r"(?<!\d)20\d{7}(?!\d)")


def mask_pii(text: str) -> str:
    """Mask phone/email/student-id patterns in place.

    전화번호·이메일·학번 패턴을 마스킹한다.
    Applied right before every messages.content insert — the user sees the
    masked version too (single-storage principle).
    모든 messages.content 기록 직전에 적용 — 사용자 화면에도 마스킹본이
    보인다 (단일 저장 원칙).
    """
    text = _EMAIL.sub("[이메일]", text)
    text = _PHONE.sub("[전화]", text)
    text = _STUDENT_ID.sub("[학번]", text)
    return text
