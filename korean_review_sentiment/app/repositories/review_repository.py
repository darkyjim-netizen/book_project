
from sqlalchemy.orm import Session

from sqlalchemy import desc, func

from app.models.review import Review


class ReviewRepository:

    def __init__(self, db: Session):

        self.db = db

    def save(self, review: Review):

        self.db.add(review)

        self.db.commit()

        self.db.refresh(review)

        return review

    def find_all(self):

        return (
            self.db.query(Review)
            .order_by(desc(Review.created_at))
            .all()
        )

    def find_by_id(self, review_id: int):

        return (
            self.db.query(Review)
            .filter(Review.id == review_id)
            .first()
        )

    def get_statistics(self):

        total = self.db.query(Review).count()

        positive = (
            self.db.query(Review)
            .filter(Review.sentiment == "긍정")
            .count()
        )

        negative = (
            self.db.query(Review)
            .filter(Review.sentiment == "부정")
            .count()
        )

        return {
            "total": total,
            "positive": positive,
            "negative": negative
        }