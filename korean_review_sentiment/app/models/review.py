from datetime import datetime

from sqlalchemy import (
    Integer,
    String,
    Text,
    Float,
    DateTime
)

from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Review(Base):

    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    review_text: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    sentiment: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )

    negative_score: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )

    positive_score: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        nullable=False
    )