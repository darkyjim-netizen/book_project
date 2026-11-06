import os
from datetime import datetime, timezone
from uuid import uuid4

from jwt import JWT
from jwt.jwk import OctetJWK
from jwt.exceptions import JWTException

from app.auth.auth_schemas import TokenResponse
from app.core.api_errors import api_error


ISSUER = "bookstore-api"
JWT_CODEC = JWT()


def signing_key():
    secret = os.getenv("JWT_SECRET") or os.environ["SESSION_SECRET"]
    return OctetJWK(secret.encode("utf-8"))


def issue_tokens(member_id: int) -> TokenResponse:
    now = int(datetime.now(timezone.utc).timestamp())

    def encode(kind: str, lifetime: int) -> str:
        return JWT_CODEC.encode(
            {"iss": ISSUER, "sub": str(member_id), "iat": now, "exp": now + lifetime,
             "kind": kind, "jti": uuid4().hex},
            signing_key(),
            alg="HS256",
        )

    return TokenResponse(
        access_token=encode("access", 15 * 60),
        refresh_token=encode("refresh", 7 * 24 * 60 * 60),
    )


def token_member_id(token: str, kind: str) -> int:
    try:
        payload = JWT_CODEC.decode(token, signing_key(), algorithms={"HS256"})
        if payload["iss"] != ISSUER or payload["kind"] != kind or type(payload["exp"]) is not int:
            raise ValueError
        return int(payload["sub"])
    except (JWTException, KeyError, ValueError, TypeError):
        raise api_error(401, "UNAUTHORIZED_ACCESS", "유효한 인증 토큰이 필요합니다.") from None
