from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud.product_crud import find_product, list_products
from app.database import get_db
from app.models.product_model import Review
from app.routers.product_schemas import ProductResponse


router = APIRouter(prefix="/api/ai", tags=["AI"])
# 리뷰에서 긍정 표현으로 집계할 문자열 목록입니다.
POSITIVE = ("좋았", "좋아요", "따뜻", "흥미", "여운", "인상적", "추천")
# 리뷰에서 부정 표현으로 집계할 문자열 목록입니다.
NEGATIVE = ("아쉬", "지루", "어려웠", "불편", "실망")


# 추천 도서 목록과 추천에 사용한 기준을 반환하는 형식입니다.
class AIRecommendationResponse(BaseModel):
    items: list[ProductResponse]
    strategy: str


# 리뷰 수와 긍정·부정 키워드의 집계 결과를 반환하는 형식입니다.
class SentimentResponse(BaseModel):
    product_id: int
    review_count: int
    positive_ratio: float | None
    negative_ratio: float | None
    positive_keywords: dict[str, int]
    negative_keywords: dict[str, int]


# 선택한 카테고리에서 최신 등록 도서를 추천 목록으로 반환합니다.
@router.get("/recommendations", response_model=AIRecommendationResponse)
def recommendations(db: Session = Depends(get_db), size: int = Query(10, ge=1, le=50),
                    category_id: int | None = Query(None, gt=0)):
    items, _ = list_products(db, 1, size, "created_at", "desc", None, category_id)
    return {"items": items, "strategy": "recent_products"}


# 리뷰에 포함된 키워드 출현 리뷰 수를 합산하여 긍정·부정 비율을 계산합니다.
@router.get("/reviews/{product_id}/sentiment", response_model=SentimentResponse)
def sentiment(product_id: int, db: Session = Depends(get_db)):
    # 존재하며 판매 중인 도서인지 확인한 뒤 리뷰를 조회합니다.
    find_product(db, product_id)
    reviews = list(db.scalars(select(Review.body).where(Review.product_id == product_id)))

    # 각 키워드가 포함된 리뷰 수를 세고 한 번도 나오지 않은 단어는 제외합니다.
    def keywords(words: tuple[str, ...]) -> dict[str, int]:
        return {word: count for word in words if (count := sum(word in body for body in reviews))}

    positive = keywords(POSITIVE)
    negative = keywords(NEGATIVE)
    # 긍정·부정 키워드 집계 합계를 비율의 분모로 사용합니다.
    total = sum(positive.values()) + sum(negative.values())
    # 집계된 키워드가 없으면 비율을 계산하지 않고 None을 반환합니다.
    return SentimentResponse(
        product_id=product_id, review_count=len(reviews),
        positive_ratio=sum(positive.values()) / total if total else None,
        negative_ratio=sum(negative.values()) / total if total else None,
        positive_keywords=positive, negative_keywords=negative,
    )
