"""회원가입, 로그인 등 인증 관련 API 경로."""
from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.orm import Session
from pydantic import EmailStr

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
def check_email(email: EmailStr, db: Session = Depends(get_db)):
    """이메일을 사용할 수 있는지 확인한다."""

    available = AuthService(db).check_email_available(email)

    # 사용자가 확인한 이메일과 사용 가능 여부를 반환한다.
    return {"email": email, "available": available}


@router.get("/check-name", response_model=dict, summary="이름 중복 확인")
def check_name(name: str = Query(..., min_length=1, max_length=60), db: Session = Depends(get_db)):
    return {"name": name.strip(), "available": AuthService(db).check_name_available(name)}


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


@router.post(
    "/password/reset",
    response_model=dict,
    summary="임시 비밀번호 발급",
)
def reset_password(payload: PasswordResetRequest, db: Session = Depends(get_db)):
    """임시 비밀번호를 발급한다."""

    # 서비스가 임시 비밀번호를 생성하고 해시 형태로 DB에 저장한다.
    temp = AuthService(db).issue_temp_password(payload.email)

    body = {
        "message": "임시 비밀번호가 발급되었습니다. 메일을 확인해 주세요."
    }

    # 개발 환경에서는 확인하기 편하도록 응답에 임시 비밀번호를 포함한다.
    # 운영 환경에서는 응답에 넣지 않고 메일 등 별도 전달 방식을 사용한다.
    if not settings.is_production:
        body["temp_password"] = temp

    return body


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