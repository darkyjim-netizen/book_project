# app/auth/session_router.py

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.session_dependencies import get_current_member
from app.models.user_model import Member
from app.routers.member_schemas import LoginRequest, MemberCreate, MemberResponse
from app.core.security import verify_password
from app.crud.user_crud import (
    create_member,
    get_member_by_username,
)

router = APIRouter(prefix="/auth", tags=["인증"])


# 새로운 회원 계정을 생성(회원가입)합니다.
@router.post(
    "/register",
    response_model=MemberResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    data: MemberCreate,
    db: Session = Depends(get_db),
):
    try:
        return create_member(db, data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


# 아이디와 비밀번호를 검증하고 세션을 생성하여 로그인합니다.
@router.post("/login")
def login(
    data: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    member = get_member_by_username(db, data.username)

    if (
        member is None
        or not verify_password(
            data.password,
            member.password_hash,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="아이디 또는 비밀번호가 올바르지 않습니다.",
        )

    # 로그인 전 세션을 초기화하여 세션 고정 위험을 줄입니다.
    request.session.clear()
    request.session["member_id"] = member.id

    return {
        "message": "로그인되었습니다.",
        "member": MemberResponse.model_validate(member),
    }


# 세션을 초기화하여 로그아웃 처리합니다.
@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"message": "로그아웃되었습니다."}


# 현재 인증된(로그인된) 회원의 정보를 조회합니다.
@router.get("/me", response_model=MemberResponse)
def auth_me(
    member: Member = Depends(get_current_member),
):
    return member