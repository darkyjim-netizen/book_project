# app/routers/admin.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.models import Member
from app.schemas import (
    AdminMemberUpdate,
    MemberListResponse,
    MemberResponse,
)
from app.services.members import list_members

router = APIRouter(
    prefix="/admin/members",
    tags=["관리자 - 회원 관리"],
)


@router.get("", response_model=MemberListResponse)
def admin_list_members(
    page: int = 1,
    size: int = 20,
    db: Session = Depends(get_db),
    _admin: Member = Depends(require_admin),
):
    if page < 1 or size < 1 or size > 100:
        raise HTTPException(
            status_code=422,
            detail="page는 1 이상, size는 1~100이어야 합니다.",
        )

    items, total = list_members(db, page, size)

    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
    }


@router.get("/{member_id}", response_model=MemberResponse)
def admin_read_member(
    member_id: int,
    db: Session = Depends(get_db),
    _admin: Member = Depends(require_admin),
):
    member = db.get(Member, member_id)

    if member is None:
        raise HTTPException(
            status_code=404,
            detail="회원을 찾을 수 없습니다.",
        )

    return member


@router.patch("/{member_id}", response_model=MemberResponse)
def admin_update_member(
    member_id: int,
    data: AdminMemberUpdate,
    db: Session = Depends(get_db),
    admin: Member = Depends(require_admin),
):
    member = db.get(Member, member_id)

    if member is None:
        raise HTTPException(
            status_code=404,
            detail="회원을 찾을 수 없습니다.",
        )

    changes = data.model_dump(exclude_unset=True)

    # 실습에서는 자기 자신의 관리자 권한을 해제하거나
    # 자기 계정을 비활성화하는 것을 방지합니다.
    if member.id == admin.id:
        if changes.get("role") == "member":
            raise HTTPException(
                status_code=400,
                detail="현재 로그인한 관리자의 권한은 이 API로 해제할 수 없습니다.",
            )

        if changes.get("is_active") is False:
            raise HTTPException(
                status_code=400,
                detail="현재 로그인한 관리자는 직접 비활성화할 수 없습니다.",
            )

    for field, value in changes.items():
        setattr(member, field, value)

    try:
        db.commit()
        db.refresh(member)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="회원 정보가 DB 제약 조건과 충돌합니다.",
        ) from exc

    return member


@router.delete("/{member_id}")
def admin_delete_member(
    member_id: int,
    db: Session = Depends(get_db),
    admin: Member = Depends(require_admin),
):
    member = db.get(Member, member_id)

    if member is None:
        raise HTTPException(
            status_code=404,
            detail="회원을 찾을 수 없습니다.",
        )

    if member.id == admin.id:
        raise HTTPException(
            status_code=400,
            detail="현재 로그인한 관리자 계정은 삭제할 수 없습니다.",
        )

    db.delete(member)
    db.commit()

    return {"message": "회원이 삭제되었습니다."}