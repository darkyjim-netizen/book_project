# app/dependencies.py

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Member


def get_current_member(
    request: Request,
    db: Session = Depends(get_db),
) -> Member:
    member_id = request.session.get("member_id")

    if member_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="로그인이 필요합니다.",
        )

    member = db.get(Member, member_id)

    if member is None or not member.is_active:
        request.session.clear()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효한 회원 세션이 아닙니다.",
        )

    return member


def require_admin(
    member: Member = Depends(get_current_member),
) -> Member:
    if member.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다.",
        )

    return member