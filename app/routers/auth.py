# app/routers/auth.py

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_member
from app.models import Member
from app.schemas import LoginRequest, MemberCreate, MemberResponse
from app.security import verify_password
from app.services.members import (
    create_member,
    get_member_by_username,
)

router = APIRouter(prefix="/auth", tags=["인증"])


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

    if not member.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="비활성화된 계정입니다.",
        )

    # 로그인 전 세션을 초기화하여 세션 고정 위험을 줄입니다.
    request.session.clear()
    request.session["member_id"] = member.id

    return {
        "message": "로그인되었습니다.",
        "member": MemberResponse.model_validate(member),
    }


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"message": "로그아웃되었습니다."}


@router.get("/me", response_model=MemberResponse)
def auth_me(
    member: Member = Depends(get_current_member),
):
    return member