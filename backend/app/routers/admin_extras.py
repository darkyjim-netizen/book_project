"""관리자 리뷰 조회와 쿠폰 관리."""
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import BusinessError, NotFoundError
from app.core.security import require_admin
from app.models.member import Member
from app.models.promotion import Coupon
from app.models.review import Review, ReviewSentiment

router = APIRouter(prefix='/admin', tags=['관리자 운영'])


class CouponCreate(BaseModel):
    code: str = Field(min_length=1, max_length=40, pattern=r'^[A-Za-z0-9_-]+$')
    name: str = Field(min_length=1, max_length=120)
    coupon_type: Literal['AMOUNT', 'PERCENT', 'FREESHIP']
    discount_value: float = Field(ge=0, le=99999999)
    max_discount: float | None = Field(default=None, ge=0)
    min_order_amount: float = Field(default=0, ge=0)
    total_quantity: int | None = Field(default=None, ge=1)
    valid_to: datetime

    @model_validator(mode='after')
    def validate_coupon(self):
        if self.coupon_type == 'PERCENT' and not 0 < self.discount_value <= 100:
            raise ValueError('할인율은 0보다 크고 100 이하여야 합니다.')
        if self.coupon_type == 'AMOUNT' and self.discount_value <= 0:
            raise ValueError('할인 금액은 0보다 커야 합니다.')
        if self.valid_to.tzinfo is None or self.valid_to <= datetime.now(timezone.utc):
            raise ValueError('종료 시각은 시간대가 포함된 미래 시각이어야 합니다.')
        return self


class CouponActive(BaseModel):
    is_active: bool


def coupon_data(c):
    return {'coupon_id': c.coupon_id, 'code': c.code, 'name': c.name,
            'coupon_type': c.coupon_type.value, 'discount_value': float(c.discount_value),
            'max_discount': float(c.max_discount) if c.max_discount is not None else None,
            'min_order_amount': float(c.min_order_amount), 'total_quantity': c.total_quantity,
            'issued_count': c.issued_count, 'valid_to': c.valid_to, 'is_active': c.is_active}


@router.post('/analysis/review-sentiment/run')
def run_review_sentiment(admin: Member = Depends(require_admin), db: Session = Depends(get_db)):
    # A transaction-scoped lock prevents concurrent full analysis jobs.
    if not db.scalar(text("SELECT pg_try_advisory_xact_lock(726401)")):
        raise BusinessError('이미 리뷰 분석이 진행 중입니다. 잠시 후 새로고침해 주세요.', status_code=409)
    from app.ai.sentiment import get_analyzer
    try:
        count = get_analyzer().reanalyze_all(db)
        return {'analyzed_reviews': count, 'message': '리뷰 감성분석이 완료되었습니다.'}
    except Exception:
        db.rollback()
        raise


@router.get('/analysis/review-sentiment/reviews')
def sentiment_review_results(
    label: Literal['POSITIVE', 'NEUTRAL', 'NEGATIVE'] | None = None,
    page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
    admin: Member = Depends(require_admin), db: Session = Depends(get_db),
):
    from app.models.book import Book
    conditions = [Review.is_blinded.is_(False)]
    if label:
        conditions.append(ReviewSentiment.label == label)
    query = select(ReviewSentiment, Review, Book.title).join(Review, Review.review_id == ReviewSentiment.review_id).join(Book, Book.book_id == Review.book_id).where(*conditions)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.execute(query.order_by(ReviewSentiment.analyzed_at.desc(), Review.review_id.desc()).offset((page-1)*size).limit(size)).all()
    return {'items': [{'review_id': review.review_id, 'book_title': title, 'content': review.content,
                      'label': result.label.value, 'score': float(result.score),
                      'model_version': result.model_version} for result, review, title in rows],
            'meta': {'page': page, 'total_pages': (total+size-1)//size, 'total': total}}


@router.get('/analysis/review-sentiment')
def review_sentiment_summary(admin: Member = Depends(require_admin), db: Session = Depends(get_db)):
    """저장된 분석 결과만 집계하며 분석이나 학습을 실행하지 않는다."""
    total_reviews = db.scalar(select(func.count()).select_from(Review).where(Review.is_blinded.is_(False))) or 0
    rows = db.execute(select(ReviewSentiment.label, func.count()).join(Review, Review.review_id == ReviewSentiment.review_id).where(Review.is_blinded.is_(False)).group_by(ReviewSentiment.label)).all()
    counts = {'POSITIVE': 0, 'NEUTRAL': 0, 'NEGATIVE': 0}
    for label, count in rows:
        counts[label.value] = count
    latest = db.scalar(select(func.max(ReviewSentiment.analyzed_at)))
    versions = db.scalars(select(ReviewSentiment.model_version).distinct().order_by(ReviewSentiment.model_version)).all()
    return {'total_reviews': total_reviews, 'analyzed_reviews': sum(counts.values()),
            'counts': counts, 'last_analyzed_at': latest, 'model_versions': versions}


class ReviewManagementUpdate(BaseModel):
    is_blinded: bool
    reply_content: str = Field(default='', max_length=2000)


@router.patch('/reviews/{review_id}')
def update_review_management(review_id: int, payload: ReviewManagementUpdate,
                             admin: Member = Depends(require_admin), db: Session = Depends(get_db)):
    review = db.get(Review, review_id)
    if review is None:
        raise NotFoundError('리뷰를 찾을 수 없습니다.')
    reply = payload.reply_content.strip() or None
    if review.reply_content != reply:
        review.reply_content = reply
        review.replied_at = datetime.now(timezone.utc) if reply else None
    review.is_blinded = payload.is_blinded
    db.commit()
    return {'message': '변경사항을 저장했습니다.'}


@router.get('/reviews')
def list_reviews(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
                 admin: Member = Depends(require_admin), db: Session = Depends(get_db)):
    total = db.scalar(select(func.count()).select_from(Review)) or 0
    rows = db.scalars(select(Review).order_by(Review.created_at.desc(), Review.review_id.desc()).offset((page-1)*size).limit(size)).unique().all()
    return {'items': [{'review_id': r.review_id, 'book_title': r.book.title if r.book else '',
                       'member_name': (r.member.nickname or r.member.name) if r.member else '회원',
                       'rating': r.rating, 'content': r.content, 'is_blinded': r.is_blinded,
                       'reply_content': r.reply_content, 'created_at': r.created_at} for r in rows],
            'meta': {'page': page, 'total': total, 'total_pages': (total+size-1)//size}}


@router.get('/coupons')
def list_coupons(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
                 admin: Member = Depends(require_admin), db: Session = Depends(get_db)):
    total = db.scalar(select(func.count()).select_from(Coupon)) or 0
    rows = db.scalars(select(Coupon).order_by(Coupon.coupon_id.desc()).offset((page-1)*size).limit(size)).all()
    return {'items': [coupon_data(c) for c in rows], 'meta': {'page': page, 'total': total, 'total_pages': (total+size-1)//size}}


@router.post('/coupons', status_code=201)
def create_coupon(payload: CouponCreate, admin: Member = Depends(require_admin), db: Session = Depends(get_db)):
    coupon = Coupon(**payload.model_dump(), is_active=True)
    db.add(coupon)
    db.commit()
    db.refresh(coupon)
    return coupon_data(coupon)


@router.patch('/coupons/{coupon_id}')
def set_coupon_active(coupon_id: int, payload: CouponActive, admin: Member = Depends(require_admin), db: Session = Depends(get_db)):
    coupon = db.get(Coupon, coupon_id)
    if coupon is None:
        raise NotFoundError('쿠폰을 찾을 수 없습니다.')
    coupon.is_active = payload.is_active
    db.commit()
    db.refresh(coupon)
    return coupon_data(coupon)
