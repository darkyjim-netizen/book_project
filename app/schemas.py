# app/schemas.py
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# 회원가입 시 클라이언트로부터 전달받을 데이터의 유효성 검사 스키마입니다.
class MemberCreate(BaseModel):
    username: str = Field(min_length=4, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=100)

# 특수문자 입력
@field_validator("password")
@classmethod
def password_special_char(cls, value: str) -> str:
    special_chars = "!@#$%^&*(),.?\":{}|<>"
    
    if not any(char in special_chars for char in value):
        raise ValueError("비밀번호는 특수문자를 최소 1개 이상 포함해야 합니다.")
    if not any(c.isdigit() for c in value):
            raise ValueError("비밀번호는 숫자를 최소 1개 이상 포함해야 합니다.")
    return value

# 로그인 요청 시 클라이언트로부터 전달받을 아이디와 비밀번호 스키마입니다.
class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


# 회원 정보 수정(마이페이지 등) 시 선택적으로 수정할 필드들을 정의한 스키마입니다.
class MemberUpdate(BaseModel):
    email: EmailStr | None = None
    display_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )


# 데이터베이스의 회원 모델(ORM)을 클라이언트에 응답용 데이터로 변환할 때 사용하는 스키마입니다.
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


# 회원 목록을 페이징 처리하여 응답할 때 사용하는 목록 컨테이너 스키마입니다.
class MemberListResponse(BaseModel):
    items: list[MemberResponse]
    total: int
    page: int
    size: int


# 관리자가 특정 회원의 권한(role)이나 활성화 상태(is_active)를 변경할 때 사용하는 스키마입니다.
class AdminMemberUpdate(BaseModel):
    role: Literal["member", "admin"] | None = None
    is_active: bool | None = None