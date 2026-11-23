"""회원가입, 로그인 등 인증 관련 API 경로."""
from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings  # 쿠키 만료 시간과 운영 환경 여부
from app.core.database import get_db  # 요청 중 사용할 DB 세션 제공
from app.core.security import get_current_member  # 현재 로그인한 회원 확인
from app.models.member import Member
from app.schemas.common import MessageResponse
from app.schemas.member import (
    LoginRequest,
    MemberResponse,
    PasswordChangeRequest,
    PasswordResetRequest,
    RefreshRequest,
    SignupRequest,
    TokenResponse,
    WithdrawRequest,
)
from app.services.auth_service import AuthService  # 인증 관련 실제 처리 담당

# 이 라우터의 주소 앞에는 /auth가 붙고,
# API 문서에서는 "인증" 그룹으로 표시된다.
router = APIRouter(prefix="/auth", tags=["인증"])


@router.post(
    "/signup",
    response_model=MemberResponse,  # 응답을 회원 정보 형식으로 제한한다.
    status_code=status.HTTP_201_CREATED,  # 새 데이터가 만들어졌음을 나타내는 상태 코드
    summary="회원가입",
)
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    """회원가입을 처리하고 생성된 회원 정보를 반환한다."""

    # 가입, 비밀번호 해시 처리, 포인트·쿠폰 지급은 서비스에 맡긴다.
    member = AuthService(db).signup(payload)

    # ORM 회원 객체를 API 응답 스키마로 변환한다.
    return MemberResponse.model_validate(member)


@router.get(
    "/check-email",
    response_model=dict,
    summary="이메일 중복 확인",
)
def check_email(email: str, db: Session = Depends(get_db)):
    """이메일을 사용할 수 있는지 확인한다."""

    available = AuthService(db).check_email_available(email)

    # 사용자가 확인한 이메일과 사용 가능 여부를 반환한다.
    return {"email": email, "available": available}

@router.get(
    "/check-nickname",
    response_model=dict,
    summary="닉네임 중복 확인",
)
def check_nickname(nickname: str, db: Session = Depends(get_db)):
    """닉네임을 사용할 수 있는지 확인한다."""

    available = AuthService(db).check_nickname_available(nickname)

    # 사용자가 확인한 닉네임과 사용 가능 여부를 반환한다.
    return {"nickname": nickname, "available": available}

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="로그인",
)
def login(
    payload: LoginRequest,  # 이메일과 비밀번호
    request: Request,       # IP와 브라우저 정보를 읽을 때 사용
    response: Response,     # 로그인 토큰 쿠키를 설정할 때 사용
    db: Session = Depends(get_db),
):
    """로그인하고 토큰과 회원 정보를 반환한다."""

    # 서비스에서 계정과 비밀번호를 확인하고 로그인 기록과 토큰을 만든다.
    result = AuthService(db).login(
        payload,
        # 요청에 연결된 클라이언트 정보가 있으면 IP 주소를 전달한다.
        ip=request.client.host if request.client else None,
        # 로그인 기록에 브라우저 정보를 남긴다.
        user_agent=request.headers.get("user-agent"),
    )

    # 브라우저가 자바스크립트로 읽지 못하도록 HttpOnly 쿠키에 액세스 토큰을 저장한다.
    response.set_cookie(
        key="access_token",
        value=result["access_token"],
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # 만료 시간은 초 단위
        samesite="lax",  # 다른 사이트에서 온 일부 요청에 쿠키가 전송되지 않게 한다.
        secure=settings.is_production,  # 운영 환경에서는 HTTPS 연결에서만 쿠키를 보낸다.
    )

    # 로그인 전에 비회원으로 담아둔 장바구니가 있으면 회원 장바구니에 합친다.
    session_key = request.cookies.get("cart_session")
    if session_key:
        # 장바구니 기능은 이 경로에서 사용할 때만 불러온다.
        from app.services.cart_service import CartService

        CartService(db).merge_session_cart(result["member"], session_key)

    # 토큰과 공개 가능한 회원 정보를 정해진 응답 형식으로 반환한다.
    return TokenResponse(
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
        expires_in=result["expires_in"],
        member=MemberResponse.model_validate(result["member"]),
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="토큰 재발급",
)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    """리프레시 토큰을 확인하고 새 토큰을 발급한다."""

    result = AuthService(db).refresh(payload.refresh_token)

    return TokenResponse(
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
        expires_in=result["expires_in"],
        member=MemberResponse.model_validate(result["member"]),
    )


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="로그아웃",
)
def logout(response: Response):
    """브라우저에 저장된 액세스 토큰 쿠키를 지운다."""

    response.delete_cookie("access_token")
    return MessageResponse(message="로그아웃되었습니다.")


@router.get(
    "/me",
    response_model=MemberResponse,
    summary="내 정보 조회",
)
def me(member: Member = Depends(get_current_member)):
    """로그인된 회원의 정보를 반환한다."""

    # get_current_member가 토큰을 확인해 현재 회원을 가져온다.
    return MemberResponse.model_validate(member)


@router.put(
    "/password",
    response_model=MessageResponse,
    summary="비밀번호 변경",
)
def change_password(
    payload: PasswordChangeRequest,  # 현재 비밀번호와 새 비밀번호
    member: Member = Depends(get_current_member),  # 로그인한 회원
    db: Session = Depends(get_db),
):
    """현재 비밀번호를 확인하고 새 비밀번호를 저장한다."""

    AuthService(db).change_password(
        member,
        payload.current_password,
        payload.new_password,
    )
    return MessageResponse(message="비밀번호가 변경되었습니다.")


# 비밀번호 찾기(임시 비밀번호 발급) API는 메일 발송 없이 이메일만으로 남의 비밀번호를
# 바꿀 수 있어 보안상 제거했다. 로그인 5회 실패 시 정지 + 관리자 해제로 대체한다.
@router.post(
    "/withdraw",
    response_model=MessageResponse,
    summary="회원 탈퇴",
)
def withdraw(
    payload: WithdrawRequest,  # 탈퇴 사유
    response: Response,  # 탈퇴 뒤 로그인 쿠키를 제거하기 위해 사용
    member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    """회원 탈퇴를 처리하고 브라우저의 액세스 토큰 쿠키를 지운다."""

    # 탈퇴 이력 저장과 개인정보 처리는 서비스에서 수행한다.
    AuthService(db).withdraw(
        member,
        payload.reason_code,
        payload.reason_text,
    )

    # 탈퇴한 회원이 기존 쿠키로 계속 인증되지 않도록 쿠키를 삭제한다.
    response.delete_cookie("access_token")

    return MessageResponse(message="탈퇴 처리가 완료되었습니다.")

# ======================================================================
# 구글 소셜 로그인
#
# 흐름: 로그인 화면 [Google로 로그인] 버튼
#   → GET /api/v1/auth/google/login?origin=<화면 주소>   (구글 로그인 페이지로 이동)
#   → 구글에서 계정 선택
#   → GET /api/v1/auth/google/callback?code=...&state=... (구글이 돌려보냄)
#   → 회원 조회/연결/가입 후 access_token 쿠키를 심고 화면으로 이동
#
# 구글 콘솔의 "승인된 리디렉션 URI"에는 <화면 주소>/api/v1/auth/google/callback 을
# 화면 주소마다 등록해야 한다. 예) http://localhost:5173/..., http://localhost:8080/...
# ======================================================================
import logging as _logging
import secrets as _secrets
from urllib.parse import urlencode, urlparse

import requests as _requests
from fastapi import HTTPException, Query
from fastapi.responses import RedirectResponse

from app.core.exceptions import BusinessError
from app.core.security import _create_token, decode_token

_google_logger = _logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GOOGLE_NONCE_COOKIE = "google_oauth_nonce"


def _google_origin(origin: str) -> str:
    """로그인을 시작한 화면 주소를 검사하고 'scheme://host[:port]' 형태로 돌려준다.

    아무 주소로나 돌려보내지 않도록 localhost, *.trycloudflare.com,
    GOOGLE_ALLOWED_ORIGINS에 적힌 주소만 허용한다.
    """
    parsed = urlparse((origin or "").strip())
    if not parsed.scheme or not parsed.hostname or parsed.path not in ("", "/") or parsed.query:
        raise BusinessError("허용되지 않은 로그인 주소입니다.", code="OAUTH_BAD_ORIGIN")
    normalized = f"{parsed.scheme}://{parsed.netloc}"
    host = parsed.hostname
    extra = [o.strip().rstrip("/") for o in settings.GOOGLE_ALLOWED_ORIGINS.split(",") if o.strip()]
    allowed = (
        (parsed.scheme == "http" and host in ("localhost", "127.0.0.1"))
        or (parsed.scheme == "https" and host.endswith(".trycloudflare.com"))
        or normalized in extra
    )
    if not allowed:
        raise BusinessError("허용되지 않은 로그인 주소입니다.", code="OAUTH_BAD_ORIGIN")
    return normalized


def _google_redirect_uri(origin: str) -> str:
    return f"{origin}{settings.API_PREFIX}/auth/google/callback"


def _login_error_redirect(message: str) -> RedirectResponse:
    """로그인 화면으로 돌려보내며 오류 문구를 보여준다. (콜백과 화면은 같은 주소)"""
    response = RedirectResponse(f"/login?{urlencode({'oauth_error': message})}", status_code=302)
    response.delete_cookie(GOOGLE_NONCE_COOKIE)
    return response


@router.get("/google/login", summary="구글 로그인 시작")
def google_login(origin: str = Query(..., description="로그인 화면의 주소. 예) http://localhost:5173")):
    """구글 로그인 페이지로 이동시킨다."""

    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise BusinessError("구글 로그인 설정(GOOGLE_CLIENT_ID/SECRET)이 없습니다.", status_code=503)

    origin = _google_origin(origin)

    # state: 위조 방지용 값. 서명된 토큰에 화면 주소와 nonce를 담고,
    # 같은 nonce를 쿠키에도 저장해 콜백에서 둘이 같은지 확인한다.
    nonce = _secrets.token_urlsafe(16)
    state = _create_token({"origin": origin, "nonce": nonce}, 10, "google_state")

    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": _google_redirect_uri(origin),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    }
    response = RedirectResponse(f"{GOOGLE_AUTH_URL}?{urlencode(params)}", status_code=302)
    response.set_cookie(
        key=GOOGLE_NONCE_COOKIE,
        value=nonce,
        httponly=True,
        max_age=600,
        samesite="lax",
        secure=origin.startswith("https://"),
    )
    return response


@router.get("/google/callback", summary="구글 로그인 콜백", include_in_schema=False)
def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    """구글이 돌려준 code로 사용자 정보를 받아 로그인 처리한다."""

    # 1) state 확인 (서명, 만료, nonce 쿠키 일치)
    try:
        data = decode_token(state) if state else None
    except HTTPException:
        data = None
    if not data or data.get("type") != "google_state":
        return _login_error_redirect("로그인 요청이 만료되었습니다. 다시 시도해 주세요.")
    if request.cookies.get(GOOGLE_NONCE_COOKIE) != data.get("nonce"):
        return _login_error_redirect("로그인 요청이 만료되었습니다. 다시 시도해 주세요.")
    if error or not code:
        return _login_error_redirect("구글 로그인이 취소되었습니다.")

    origin = data["origin"]

    # 2) code → 구글 액세스 토큰 → 사용자 정보
    try:
        token_res = _requests.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": _google_redirect_uri(origin),
                "grant_type": "authorization_code",
            },
            timeout=10,
        )
        if token_res.status_code != 200:
            _google_logger.warning("구글 토큰 교환 실패: %s %s", token_res.status_code, token_res.text[:300])
            return _login_error_redirect("구글 인증에 실패했습니다. 다시 시도해 주세요.")
        google_access_token = token_res.json().get("access_token")

        info_res = _requests.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {google_access_token}"},
            timeout=10,
        )
        info_res.raise_for_status()
        info = info_res.json()
    except _requests.RequestException:
        _google_logger.exception("구글 서버 통신 실패")
        return _login_error_redirect("구글 서버와 통신하지 못했습니다. 잠시 후 다시 시도해 주세요.")

    if not info.get("sub") or not info.get("email") or not info.get("email_verified"):
        return _login_error_redirect("이메일 인증이 완료된 구글 계정만 사용할 수 있습니다.")

    # 3) 회원 찾기/연결/가입 + 토큰 발급
    try:
        result = AuthService(db).login_with_google(
            google_id=str(info["sub"]),
            email=info["email"],
            name=info.get("name"),
            picture=info.get("picture"),
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except BusinessError as exc:
        db.rollback()
        return _login_error_redirect(exc.message)

    member = result["member"]

    # 4) 비회원 장바구니 합치기 (일반 로그인과 동일)
    session_key = request.cookies.get("cart_session")
    if session_key:
        from app.services.cart_service import CartService

        CartService(db).merge_session_cart(member, session_key)

    # 5) 일반 로그인과 같은 access_token 쿠키를 심고 화면으로 이동
    is_admin = member.role.value in ("ADMIN", "STAFF")
    response = RedirectResponse("/store-admin/dashboard" if is_admin else "/main", status_code=302)
    response.set_cookie(
        key="access_token",
        value=result["access_token"],
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=settings.is_production,
    )
    response.delete_cookie(GOOGLE_NONCE_COOKIE)
    return response
