# app/routers/members.py

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_member
from app.models import Member
from app.schemas import MemberResponse, MemberUpdate

router = APIRouter(prefix="/members", tags=["회원"])


# 현재 로그인한 회원의 프로필 정보를 조회합니다.
@router.get("/me", response_model=MemberResponse)
def read_my_profile(
    member: Member = Depends(get_current_member),
):
    return member


# 현재 로그인한 회원의 프로필 정보(이메일, 닉네임 등)를 수정합니다.
@router.patch("/me", response_model=MemberResponse)
def update_my_profile(
    data: MemberUpdate,
    db: Session = Depends(get_db),
    member: Member = Depends(get_current_member),
):
    changes = data.model_dump(exclude_unset=True)

    if "email" in changes and changes["email"] is not None:
        email = str(changes["email"])

        duplicate = db.scalar(
            select(Member).where(
                Member.email == email,
                Member.id != member.id,
            )
        )

        if duplicate:
            raise HTTPException(
                status_code=409,
                detail="이미 사용 중인 이메일입니다.",
            )

        member.email = email

    if (
        "display_name" in changes
        and changes["display_name"] is not None
    ):
        member.display_name = changes["display_name"]

    try:
        db.commit()
        db.refresh(member)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="회원 정보가 다른 데이터와 충돌합니다.",
        ) from exc

    return member


# 현재 로그인한 회원의 계정을 삭제(회원 탈퇴)하고 세션을 초기화합니다.
@router.delete("/me")
def delete_my_account(
    request: Request,
    db: Session = Depends(get_db),
    member: Member = Depends(get_current_member),
):
    db.delete(member)
    db.commit()

    request.session.clear()

    return {"message": "회원 탈퇴가 완료되었습니다."}