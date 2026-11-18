"""인증/인가 유틸리티.

- 비밀번호 해싱(bcrypt)
- JWT 액세스/리프레시 토큰 발급 및 검증
- 현재 사용자 조회 및 관리자 권한 확인
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db


# 비밀번호 해시 생성과 검증에 bcrypt를 사용한다.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Bearer 토큰이 없어도 즉시 오류를 반환하지 않으므로 쿠키를 확인할 수 있다.
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_PREFIX}/auth/login",
    auto_error=False,
)


# 비밀번호
def hash_password(raw_password: str) -> str:
    """평문 비밀번호를 bcrypt 해시로 변환한다."""
    return pwd_context.hash(raw_password)


def verify_password(raw_password: str, hashed: Optional[str]) -> bool:
    """입력한 비밀번호가 저장된 해시와 일치하는지 확인한다."""
    if not hashed:
        return False

    try:
        return pwd_context.verify(raw_password, hashed)
    except ValueError:
        return False


def validate_password_policy(raw_password: str) -> None:
    """비밀번호 정책을 확인하고 조건을 충족하지 않으면 HTTP 400을 반환한다."""
    if len(raw_password) < settings.PASSWORD_MIN_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"비밀번호는 최소 {settings.PASSWORD_MIN_LENGTH}자 이상이어야 합니다.",
        )

    # isalpha()는 한글 등 유니코드 문자도 글자로 판정한다.
    has_alpha = any(c.isalpha() for c in raw_password)
    has_digit = any(c.isdigit() for c in raw_password)
    if not (has_alpha and has_digit):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="비밀번호는 영문과 숫자를 모두 포함해야 합니다.",
        )


# JWT
def _create_token(
    payload: Dict[str, Any], expires_minutes: int, token_type: str
) -> str:
    now = datetime.now(timezone.utc)

    # 원본 페이로드를 복사한 뒤 발급 시각, 만료 시각, 토큰 종류를 추가한다.
    to_encode = payload.copy()
    to_encode.update(
        {
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=expires_minutes)).timestamp()),
            "type": token_type,
        }
    )
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(member_id: int, email: str, role: str) -> str:
    """API 인증에 사용하는 액세스 토큰을 발급한다."""
    return _create_token(
        {"sub": str(member_id), "email": email, "role": role},
        settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        "access",
    )


def create_refresh_token(member_id: int) -> str:
    """액세스 토큰 재발급에 사용하는 리프레시 토큰을 발급한다."""
    return _create_token(
        {"sub": str(member_id)},
        settings.REFRESH_TOKEN_EXPIRE_MINUTES,
        "refresh",
    )


def create_guest_order_token(order_id: int) -> str:
    """비회원 주문 한 건에만 사용할 수 있는 서명 토큰을 발급한다."""
    return _create_token(
        {"order_id": order_id},
        expires_minutes=120,
        token_type="guest_order",
    )


def decode_token(token: str) -> Dict[str, Any]:
    """JWT 서명과 만료 시각을 검증하고 페이로드를 반환한다."""
    try:
        return jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 토큰입니다.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# FastAPI 인증 의존성
def _extract_token(request: Request, bearer: Optional[str]) -> Optional[str]:
    """Authorization 헤더를 우선 사용하고, 없으면 쿠키를 확인한다."""
    if bearer:
        return bearer
    return request.cookies.get("access_token")


def verify_guest_order_token(token: Optional[str], order_id: int) -> None:
    """서명된 비회원 토큰이 요청한 주문에만 유효한지 확인한다."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="비회원 주문 인증 토큰이 필요합니다.",
        )

    payload = decode_token(token)
    if (
        payload.get("type") != "guest_order"
        or payload.get("order_id") != order_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="해당 주문에 접근할 수 없습니다.",
        )


def get_current_member_optional(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    """로그인이 선택 사항인 엔드포인트에서 사용한다."""
    from app.models.member import Member

    raw = _extract_token(request, token)
    if not raw:
        return None

    # 토큰이 유효하지 않거나 액세스 토큰이 아니면 비로그인 상태로 처리한다.
    try:
        payload = decode_token(raw)
    except HTTPException:
        return None

    if payload.get("type") != "access":
        return None

    # 토큰의 sub에 저장된 회원 ID로 DB를 조회한다.
    member = db.get(Member, int(payload["sub"]))
    if member is None or member.status.value == "WITHDRAWN":
        return None
    return member


def get_current_member(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    """로그인이 필수인 엔드포인트에서 현재 회원을 조회한다."""
    from app.models.member import Member

    raw = _extract_token(request, token)
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="로그인이 필요합니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(raw)
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="액세스 토큰이 아닙니다.")

    # 회원의 현재 계정 상태는 DB에서 확인한다.
    member = db.get(Member, int(payload["sub"]))
    if member is None:
        raise HTTPException(status_code=401, detail="존재하지 않는 회원입니다.")
    if member.status.value in ("WITHDRAWN", "SUSPENDED"):
        raise HTTPException(status_code=403, detail="이용이 제한된 계정입니다.")
    return member


def require_admin(member=Depends(get_current_member)):
    """관리자(ADMIN) 또는 운영자(STAFF) 권한을 요구한다."""
    if member.role.value not in ("ADMIN", "STAFF"):
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    return member


def require_superadmin(member=Depends(get_current_member)):
    """최고 관리자(ADMIN) 권한을 요구한다."""
    if member.role.value != "ADMIN":
        raise HTTPException(status_code=403, detail="최고 관리자 권한이 필요합니다.")
    return member
