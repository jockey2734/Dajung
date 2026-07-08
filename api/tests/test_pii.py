"""PII masking cases (SECURITY.md §8).

PII 마스킹 케이스 (SECURITY.md §8).
"""

from __future__ import annotations

from api.app.core.pii import mask_pii


def test_phone_masked() -> None:
    assert mask_pii("연락처는 010-9787-0867 입니다") == "연락처는 [전화] 입니다"
    assert mask_pii("01097870867로 전화") == "[전화]로 전화"


def test_email_masked() -> None:
    assert mask_pii("메일은 unha@example.com") == "메일은 [이메일]"


def test_student_id_masked() -> None:
    assert mask_pii("학번 2019310704 확인") == "학번 [학번] 확인"


def test_free_text_names_pass_through() -> None:
    # Names and club roles are operational context, not masked.
    # 이름과 동아리 직책은 업무 맥락이므로 마스킹하지 않는다.
    text = "임운하 회장이 회의에서 말했다"
    assert mask_pii(text) == text


def test_mixed_content() -> None:
    out = mask_pii("김OO(2019310704, kim@skku.edu, 010-1111-2222)")
    assert "[학번]" in out and "[이메일]" in out and "[전화]" in out
