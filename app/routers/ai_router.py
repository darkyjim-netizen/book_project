from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud.product_crud import find_product, list_products
from app.database import get_db
from app.models.product_model import Review
from app.routers.product_schemas import ProductResponse


router = APIRouter(prefix="/api/ai", tags=["AI"])
POSITIVE = ("좋았", "좋아요", "따뜻", "흥미", "여운", "인상적", "추천")
NEGATIVE = ("아쉬", "지루", "어려웠", "불편", "실망")


class AIRecommendationResponse(BaseModel):
    items: list[ProductResponse]
    strategy: str


class SentimentResponse(BaseModel):
    product_id: int
    review_count: int
    positive_ratio: float | None
    negative_ratio: float | None
    positive_keywords: dict[str, int]
    negative_keywords: dict[str, int]


@router.get("/recommendations", response_model=AIRecommendationResponse)
def recommendations(db: Session = Depends(get_db), size: int = Query(10, ge=1, le=50),
                    category_id: int | None = Query(None, gt=0)):
    items, _ = list_products(db, 1, size, "created_at", "desc", None, category_id)
    return {"items": items, "strategy": "recent_products"}


@router.get("/reviews/{product_id}/sentiment", response_model=SentimentResponse)
def sentiment(product_id: int, db: Session = Depends(get_db)):
    find_product(db, product_id)
    reviews = list(db.scalars(select(Review.body).where(Review.product_id == product_id)))

    def keywords(words: tuple[str, ...]) -> dict[str, int]:
        return {word: count for word in words if (count := sum(word in body for body in reviews))}

    positive = keywords(POSITIVE)
    negative = keywords(NEGATIVE)
    total = sum(positive.values()) + sum(negative.values())
    return SentimentResponse(
        product_id=product_id, review_count=len(reviews),
        positive_ratio=sum(positive.values()) / total if total else None,
        negative_ratio=sum(negative.values()) / total if total else None,
        positive_keywords=positive, negative_keywords=negative,
    )
