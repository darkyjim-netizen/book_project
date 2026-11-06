from datetime import datetime
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr = Field(validation_alias=AliasChoices("email", "Email"), max_length=255)
    password: str = Field(validation_alias=AliasChoices("password", "Password"), min_length=1, max_length=128)


class SignupRequest(LoginRequest):
    password: str = Field(validation_alias=AliasChoices("password", "Password"), min_length=8, max_length=128)
    name: str = Field(validation_alias=AliasChoices("name", "Name"), min_length=1, max_length=100)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=4096)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"


class MemberMeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    name: str = Field(validation_alias="display_name")
    role: Literal["member", "admin"]
    is_active: bool
    created_at: datetime
