
from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)

from sqlalchemy.orm import Session

from starlette.concurrency import run_in_threadpool

from app.core.database import get_db

from app.schemas.review_schema import (
    ReviewRequest,
    SentimentResponse
)

from app.services.review_service import ReviewService


router = APIRouter(
    prefix="/api/reviews",
    tags=["한국어 리뷰 감정 분석"]
)


@router.post(
    "/analyze",
    response_model=SentimentResponse
)
async def analyze_review(
    request: ReviewRequest,
    db: Session = Depends(get_db)
):

    text = request.review_text.strip()

    if len(text) < 2 or len(text) > 5000:

        raise HTTPException(
            status_code=400,
            detail="리뷰는 2자 이상 5,000자 이하로 입력해 주세요."
        )

    service = ReviewService(db)

    # 모델 추론은 CPU/GPU 연산이므로 스레드 풀에서 실행
    result = await run_in_threadpool(
        service.analyze_review,
        text
    )

    return result


@router.get("/history")
def get_history(
    db: Session = Depends(get_db)
):

    service = ReviewService(db)

    reviews = service.get_history()

    return [
        {
            "id": review.id,
            "review_text": review.review_text,
            "sentiment": review.sentiment,
            "confidence": review.confidence,
            "negative_score": review.negative_score,
            "positive_score": review.positive_score,
            "created_at": review.created_at.isoformat()
        }
        for review in reviews
    ]


@router.get("/statistics")
def get_statistics(
    db: Session = Depends(get_db)
):

    service = ReviewService(db)

    return service.get_statistics()