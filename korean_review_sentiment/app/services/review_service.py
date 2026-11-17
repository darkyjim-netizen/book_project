
from sqlalchemy.orm import Session

from app.models.review import Review

from app.repositories.review_repository import (
    ReviewRepository
)

from app.services.sentiment_service import (
    get_sentiment_analyzer
)


class ReviewService:

    def __init__(self, db: Session):

        self.repository = ReviewRepository(db)

        self.analyzer = get_sentiment_analyzer()

    def analyze_review(self, review_text: str):

        # 1. 인공지능 감정 분석
        result = self.analyzer.predict(review_text)

        # 2. 데이터베이스 객체 생성
        review = Review(
            review_text=result["review_text"],
            sentiment=result["sentiment"],
            confidence=result["confidence"],
            negative_score=result["negative_score"],
            positive_score=result["positive_score"]
        )

        # 3. 데이터베이스 저장
        saved_review = self.repository.save(review)

        # 4. 결과 반환
        return {
            "id": saved_review.id,
            "review_text": saved_review.review_text,
            "sentiment": saved_review.sentiment,
            "confidence": saved_review.confidence,
            "negative_score": saved_review.negative_score,
            "positive_score": saved_review.positive_score,
            "created_at": saved_review.created_at
        }

    def get_history(self):

        return self.repository.find_all()

    def get_statistics(self):

        return self.repository.get_statistics()