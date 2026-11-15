import os
from datetime import datetime, timezone
from uuid import uuid4

from jwt import JWT
from jwt.jwk import OctetJWK
from jwt.exceptions import JWTException

from app.auth.auth_schemas import TokenResponse
from app.core.api_errors import api_error


# 토큰을 발급한 서비스를 식별할 고정 이름입니다.
ISSUER = "bookstore-api"
JWT_CODEC = JWT()


# 환경 변수의 비밀 키를 JWT 서명에 사용할 키 객체로 변환합니다.
def signing_key():
    secret = os.getenv("JWT_SECRET") or os.environ["SESSION_SECRET"]
    return OctetJWK(secret.encode("utf-8"))


# 회원 ID를 담은 액세스 토큰과 리프레시 토큰을 발급합니다.
def issue_tokens(member_id: int) -> TokenResponse:
    # 토큰 발급 시각과 만료 시각 계산에 사용할 현재 UTC 시간을 구합니다.
    now = int(datetime.now(timezone.utc).timestamp())

    # 토큰 종류와 유효 기간을 담아 HS256 방식으로 서명합니다.
    def encode(kind: str, lifetime: int) -> str:
        return JWT_CODEC.encode(
            {"iss": ISSUER, "sub": str(member_id), "iat": now, "exp": now + lifetime,
             "kind": kind, "jti": uuid4().hex},
            signing_key(),
            alg="HS256",
        )

    # 액세스 토큰은 15분, 리프레시 토큰은 7일 동안 유효하게 발급합니다.
    return TokenResponse(
        access_token=encode("access", 15 * 60),
        refresh_token=encode("refresh", 7 * 24 * 60 * 60),
    )


# JWT를 검증하고 발급자와 토큰 종류를 확인한 뒤 회원 ID를 반환합니다.
def token_member_id(token: str, kind: str) -> int:
    try:
        payload = JWT_CODEC.decode(token, signing_key(), algorithms={"HS256"})
        if payload["iss"] != ISSUER or payload["kind"] != kind or type(payload["exp"]) is not int:
            raise ValueError
        return int(payload["sub"])
    # 변조되거나 형식이 잘못된 토큰을 인증 실패 응답으로 처리합니다.
    except (JWTException, KeyError, ValueError, TypeError):
        raise api_error(401, "UNAUTHORIZED_ACCESS", "유효한 인증 토큰이 필요합니다.") from None
