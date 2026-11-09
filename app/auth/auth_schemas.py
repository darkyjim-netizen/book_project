from datetime import datetime
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, EmailStr, Field


# 로그인에 필요한 이메일과 비밀번호의 입력 형식을 정의합니다.
class LoginRequest(BaseModel):
    email: EmailStr = Field(validation_alias=AliasChoices("email", "Email"), max_length=255)
    password: str = Field(validation_alias=AliasChoices("password", "Password"), min_length=1, max_length=128)


# 회원가입에 필요한 이름과 비밀번호 길이 조건을 추가합니다.
class SignupRequest(LoginRequest):
    password: str = Field(validation_alias=AliasChoices("password", "Password"), min_length=8, max_length=128)
    name: str = Field(validation_alias=AliasChoices("name", "Name"), min_length=1, max_length=100)


# 토큰 재발급 요청에 사용할 리프레시 토큰을 검증합니다.
class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=4096)


# 로그인과 재발급 응답에 포함할 인증 토큰 형식을 정의합니다.
class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"


# 회원 객체를 내 정보 조회 응답으로 변환할 필드를 정의합니다.
class MemberMeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    name: str = Field(validation_alias="display_name")
    role: Literal["member", "admin"]
    is_active: bool
    created_at: datetime
