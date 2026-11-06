# app/routers/admin_members_router.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.session_dependencies import require_admin
from app.models.user_model import Member
from app.routers.member_schemas import (
    AdminMemberUpdate,
    MemberListResponse,
    MemberResponse,
)
from app.crud.user_crud import list_members

router = APIRouter(
    prefix="/admin/members",
    tags=["관리자 - 회원 관리"],
)


# 관리자 권한으로 회원 목록을 페이지네이션하여 조회
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


# 특정 회원의 상세 정보를 조회
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


# 특정 회원의 정보를 수정, 자기 계정의 안전 장치를 검증
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

    # 자기 자신의 관리자 권한을 해제하거나
    # 자기 계정을 비활성화하는 것을 방지
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


# 특정 회원을 삭제, 자기 자신 계정의 삭제를 방지
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