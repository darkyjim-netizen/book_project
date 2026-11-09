from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import auth_service
from app.auth.auth_dependencies import current_member
from app.auth.auth_schemas import LoginRequest, MemberMeResponse, RefreshRequest, SignupRequest, TokenResponse
from app.database import get_db
from app.models.user_model import Member


router = APIRouter(prefix="/api/auth", tags=["인증"])


# 가입 정보를 검증한 뒤 회원을 생성하고 회원 정보를 반환합니다.
@router.post("/signup", status_code=201, response_model=MemberMeResponse)
def signup(data: SignupRequest, db: Session = Depends(get_db)):
    return auth_service.signup(data, db)


# 이메일과 비밀번호로 로그인하고 인증 토큰을 반환합니다.
@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    return auth_service.login(data, db)


# 리프레시 토큰으로 새로운 인증 토큰을 발급합니다.
@router.post("/refresh", response_model=TokenResponse)
def refresh(data: RefreshRequest, db: Session = Depends(get_db)):
    return auth_service.refresh(data, db)


# 액세스 토큰으로 인증된 회원의 정보를 반환합니다.
@router.get("/me", response_model=MemberMeResponse)
def me(member: Member = Depends(current_member)):
    return member
