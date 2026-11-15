# app/schemas.py

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class MemberCreate(BaseModel):
    username: str = Field(min_length=4, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=100)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


class MemberUpdate(BaseModel):
    email: EmailStr | None = None
    display_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )


class MemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    display_name: str
    role: Literal["member", "admin"]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class MemberListResponse(BaseModel):
    items: list[MemberResponse]
    total: int
    page: int
    size: int


class AdminMemberUpdate(BaseModel):
    role: Literal["member", "admin"] | None = None
    is_active: bool | None = None