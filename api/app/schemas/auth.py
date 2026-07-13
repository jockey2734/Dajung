"""Auth request/response schemas — contract per serving-plan §1.

인증 요청/응답 스키마 — serving-plan §1 계약.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SignupRequest(BaseModel):
    email: EmailStr
    # bcrypt truncates beyond 72 bytes — cap it explicitly.
    # bcrypt는 72바이트 초과를 자른다 — 명시적으로 상한을 둔다.
    password: str = Field(min_length=8, max_length=72)
    name: str = Field(min_length=1, max_length=100)
    invitation_code: str = Field(min_length=1, max_length=100)


class SignupResponse(BaseModel):
    user_id: uuid.UUID


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    name: str
    role: str
    must_change_password: bool


class SigninRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class SigninResponse(BaseModel):
    access_token: str
    user: UserOut


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=72)
    new_password: str = Field(min_length=8, max_length=72)
