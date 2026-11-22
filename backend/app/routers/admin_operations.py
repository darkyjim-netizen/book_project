"""관리자 운영 화면(AdminOperations.vue)의 리뷰 관리·쿠폰 관리 API.

- GET   /admin/reviews               : 리뷰 목록
- PATCH /admin/reviews/{review_id}   : 블라인드 여부와 답글을 한 번에 저장
- GET   /admin/coupons               : 쿠폰 목록
- POST  /admin/coupons               : 쿠폰 등록
- PATCH /admin/coupons/{coupon_id}   : 쿠폰 사용/중지
"""

from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import BusinessError, NotFoundError
from app.core.security import require_admin
from app.models.enums import CouponType
from app.models.member import Member
from app.models.promotion import Coupon
from app.models.review import Review

router = APIRouter(prefix="/admin", tags=["관리자-운영"])


def _meta(page: int, size: int, total: int) -> dict:
    return {"page": page, "size": size, "total": total, "total_pages": (total + size - 1) // size}


# -----------------------------------------------------------------------------
# 리뷰 관리
# -----------------------------------------------------------------------------
class ReviewManagementUpdate(BaseModel):
    """리뷰 관리 저장 요청. 블라인드 여부와 답글을 함께 보낸다."""

    is_blinded: bool
    reply_content: str = Field(default="", max_length=2000)


@router.get("/reviews", summary="리뷰 목록(관리자)")
def list_reviews(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """블라인드된 리뷰까지 포함해 최신순으로 반환한다."""
    total = db.scalar(select(func.count()).select_from(Review)) or 0
    rows = db.scalars(
        select(Review)
        .order_by(Review.created_at.desc(), Review.review_id.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).unique().all()
    return {
        "items": [
            {
                "review_id": r.review_id,
                "book_title": r.book.title if r.book else "",
                "member_name": (r.member.nickname or r.member.name) if r.member else "회원",
                "rating": r.rating,
                "content": r.content,
                "is_blinded": r.is_blinded,
                "reply_content": r.reply_content,
                "created_at": r.created_at,
            }
            for r in rows
        ],
        "meta": _meta(page, size, total),
    }


@router.patch("/reviews/{review_id}", summary="리뷰 관리 저장")
def update_review_management(
    review_id: int,
    payload: ReviewManagementUpdate,
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """블라인드 여부와 답글을 저장한다. 답글을 비우면 답글이 삭제된다."""
    review = db.get(Review, review_id)
    if review is None:
        raise NotFoundError("리뷰를 찾을 수 없습니다.")

    reply = payload.reply_content.strip() or None
    if review.reply_content != reply:
        review.reply_content = reply
        review.replied_at = datetime.now(timezone.utc) if reply else None
    review.is_blinded = payload.is_blinded
    db.commit()
    return {"message": "변경사항을 저장했습니다."}


# -----------------------------------------------------------------------------
# 쿠폰 관리
# -----------------------------------------------------------------------------
class CouponCreate(BaseModel):
    """쿠폰 등록 요청."""

    code: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=120)
    coupon_type: Literal["AMOUNT", "PERCENT", "FREESHIP"]
    discount_value: float = Field(ge=0, le=99999999)
    max_discount: Optional[float] = Field(default=None, ge=0)
    min_order_amount: float = Field(default=0, ge=0)
    total_quantity: Optional[int] = Field(default=None, ge=1)
    valid_to: datetime

    @model_validator(mode="after")
    def validate_coupon(self):
        if self.coupon_type == "PERCENT" and not 0 < self.discount_value <= 100:
            raise ValueError("할인율은 0보다 크고 100 이하여야 합니다.")
        if self.coupon_type == "AMOUNT" and self.discount_value <= 0:
            raise ValueError("할인 금액은 0보다 커야 합니다.")
        if self.valid_to.tzinfo is None or self.valid_to <= datetime.now(timezone.utc):
            raise ValueError("종료 시각은 시간대가 포함된 미래 시각이어야 합니다.")
        return self


class CouponActive(BaseModel):
    is_active: bool


def _coupon_data(c: Coupon) -> dict:
    return {
        "coupon_id": c.coupon_id,
        "code": c.code,
        "name": c.name,
        "coupon_type": getattr(c.coupon_type, "value", c.coupon_type),
        "discount_value": float(c.discount_value),
        "max_discount": float(c.max_discount) if c.max_discount is not None else None,
        "min_order_amount": float(c.min_order_amount or 0),
        "total_quantity": c.total_quantity,
        "issued_count": c.issued_count,
        "valid_to": c.valid_to,
        "is_active": c.is_active,
    }


@router.get("/coupons", summary="쿠폰 목록(관리자)")
def list_coupons(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    total = db.scalar(select(func.count()).select_from(Coupon)) or 0
    rows = db.scalars(
        select(Coupon).order_by(Coupon.coupon_id.desc()).offset((page - 1) * size).limit(size)
    ).all()
    return {"items": [_coupon_data(c) for c in rows], "meta": _meta(page, size, total)}


@router.post("/coupons", status_code=status.HTTP_201_CREATED, summary="쿠폰 등록")
def create_coupon(
    payload: CouponCreate,
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if db.scalar(select(func.count()).select_from(Coupon).where(Coupon.code == payload.code)):
        raise BusinessError("이미 사용 중인 쿠폰 코드입니다.", code="COUPON_CODE_DUPLICATED", status_code=409)

    data = payload.model_dump()
    data["coupon_type"] = CouponType(data["coupon_type"])
    coupon = Coupon(**data, is_active=True)
    db.add(coupon)
    db.commit()
    db.refresh(coupon)
    return _coupon_data(coupon)


@router.patch("/coupons/{coupon_id}", summary="쿠폰 사용/중지")
def set_coupon_active(
    coupon_id: int,
    payload: CouponActive,
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    coupon = db.get(Coupon, coupon_id)
    if coupon is None:
        raise NotFoundError("쿠폰을 찾을 수 없습니다.")
    coupon.is_active = payload.is_active
    db.commit()
    db.refresh(coupon)
    return _coupon_data(coupon)
