"""관리자 대시보드 '리뷰 감성 분석' API.

프론트(AdminAnalysis.vue)가 호출하는 세 경로를 제공한다.
- GET  /admin/analysis/review-sentiment          : 저장된 분석 결과 요약
- GET  /admin/analysis/review-sentiment/reviews  : 리뷰별 분석 결과 목록
- POST /admin/analysis/review-sentiment/run      : 전체 리뷰 다시 분석
"""

from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import BusinessError
from app.core.security import require_admin
from app.models.book import Book
from app.models.member import Member
from app.models.review import Review, ReviewSentiment

router = APIRouter(prefix="/admin/analysis/review-sentiment", tags=["관리자-리뷰 감성 분석"])

LABELS = ("POSITIVE", "NEUTRAL", "NEGATIVE")


@router.get("", summary="리뷰 감성 분석 요약")
def review_sentiment_summary(
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """저장된 분석 결과만 집계한다. 분석을 새로 실행하지 않는다."""
    total_reviews = db.scalar(
        select(func.count()).select_from(Review).where(Review.is_blinded.is_(False))
    ) or 0

    rows = db.execute(
        select(ReviewSentiment.label, func.count())
        .join(Review, Review.review_id == ReviewSentiment.review_id)
        .where(Review.is_blinded.is_(False))
        .group_by(ReviewSentiment.label)
    ).all()
    counts = {label: 0 for label in LABELS}
    for label, count in rows:
        counts[getattr(label, "value", label)] = count

    last_analyzed_at = db.scalar(select(func.max(ReviewSentiment.analyzed_at)))
    model_versions = db.scalars(
        select(ReviewSentiment.model_version).distinct().order_by(ReviewSentiment.model_version)
    ).all()

    return {
        "total_reviews": total_reviews,
        "analyzed_reviews": sum(counts.values()),
        "counts": counts,
        "last_analyzed_at": last_analyzed_at,
        "model_versions": list(model_versions),
    }


@router.get("/reviews", summary="리뷰별 감성 분석 결과")
def review_sentiment_results(
    label: Optional[Literal["POSITIVE", "NEUTRAL", "NEGATIVE"]] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """블라인드되지 않은 리뷰의 분석 결과를 최근 분석 순으로 반환한다."""
    query = (
        select(ReviewSentiment, Review, Book.title)
        .join(Review, Review.review_id == ReviewSentiment.review_id)
        .join(Book, Book.book_id == Review.book_id)
        .where(Review.is_blinded.is_(False))
    )
    if label:
        query = query.where(ReviewSentiment.label == label)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.execute(
        query.order_by(ReviewSentiment.analyzed_at.desc(), Review.review_id.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()

    return {
        "items": [
            {
                "review_id": review.review_id,
                "book_title": title,
                "content": review.content,
                "label": getattr(result.label, "value", result.label),
                "score": float(result.score),
                "model_version": result.model_version,
            }
            for result, review, title in rows
        ],
        "meta": {"page": page, "size": size, "total": total, "total_pages": (total + size - 1) // size},
    }


@router.post("/run", summary="리뷰 감성 분석 실행")
def run_review_sentiment(
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """블라인드되지 않은 리뷰 전체를 다시 분석해 ai.review_sentiments에 저장한다."""
    # 두 관리자가 동시에 실행하지 못하도록 트랜잭션 단위 잠금을 건다.
    if not db.scalar(text("SELECT pg_try_advisory_xact_lock(726401)")):
        raise BusinessError(
            "이미 리뷰 분석이 진행 중입니다. 잠시 후 새로고침해 주세요.",
            code="SENTIMENT_RUNNING",
            status_code=409,
        )

    from app.ai.sentiment import get_analyzer

    try:
        count = get_analyzer().reanalyze_all(db)
    except Exception:
        db.rollback()
        raise
    return {"analyzed_reviews": count, "message": "리뷰 감성분석이 완료되었습니다."}
