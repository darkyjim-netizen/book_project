# app/dependencies.py

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Member


# 세션 정보를 기반으로 현재 로그인된 사용자를 조회하고 검증하는 의존성 함수입니다.
def get_current_member(
    request: Request,
    db: Session = Depends(get_db),
) -> Member:
    member_id = request.session.get("member_id")  # 세션에서 회원 ID를 가져옵니다.

    if member_id is None:  # 로그인된 ID가 없으면 인증 에러를 발생시킵니다.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="로그인이 필요합니다.",
        )

    member = db.get(Member, member_id)  # DB에서 회원 정보를 조회합니다.

    if member is None or not member.is_active:  # 회원이 없거나 비활성화 상태면 세션을 비우고 인증 에러를 발생시킵니다.
        request.session.clear()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효한 회원 세션이 아닙니다.",
        )

    return member  # 인증된 회원 객체를 반환합니다.


# 현재 로그인된 사용자가 관리자(admin) 권한을 가지고 있는지 검증하는 의존성 함수입니다.
def require_admin(
    member: Member = Depends(get_current_member),
) -> Member:
    if member.role != "admin":  # 관리자 권한이 아니면 접근 금지 에러를 발생시킵니다.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다.",
        )

    return member  # 관리자 권한이 확인된 회원 객체를 반환합니다.