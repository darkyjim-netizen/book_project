from pydantic import BaseModel, Field


class ReviewRequest(BaseModel):

    review_text: str = Field(
        min_length=2,
        max_length=5000,
        description="한국어 상품 리뷰"
    )


class SentimentResponse(BaseModel):

    review_text: str

    sentiment: str

    confidence: float

    negative_score: float

    positive_score: float