"""리뷰와 AI 감성 분석 결과를 저장하는 ORM 모델."""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum as PgEnum,  # PostgreSQL ENUM 타입
    ForeignKey,      # 다른 테이블을 참조하는 키
    Integer,
    Numeric,         # 소수 자릿수를 지정할 수 있는 숫자 타입
    SmallInteger,
    String,
    Text,
    func,            # now() 같은 DB 함수를 표현
)
from sqlalchemy.dialects.postgresql import JSONB  # PostgreSQL의 JSON 저장 타입
from sqlalchemy.orm import Mapped, mapped_column, relationship

from team_backend.app.core.database import Base
from team_backend.app.models.enums import SentimentLabel  # POSITIVE, NEUTRAL, NEGATIVE


class Review(Base):
    """회원이 도서에 작성한 리뷰."""

    __tablename__ = "reviews"
    __table_args__ = {"schema": "shop"}

    review_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # 리뷰 번호

    # 리뷰가 작성된 도서. 도서가 삭제되면 관련 리뷰도 삭제한다.
    book_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("shop.books.book_id", ondelete="CASCADE"),
    )

    # 리뷰를 작성한 회원. 회원이 삭제되면 해당 회원의 리뷰도 삭제한다.
    member_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("shop.members.member_id", ondelete="CASCADE"),
    )

    # 구매한 상품과 리뷰를 연결할 때 사용한다. 연결 정보가 없을 수도 있다.
    order_item_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("shop.order_items.order_item_id"),
    )

    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)  # 별점
    title: Mapped[Optional[str]] = mapped_column(String(200))  # 리뷰 제목. 생략 가능
    content: Mapped[str] = mapped_column(Text, nullable=False)  # 리뷰 본문

    like_count: Mapped[int] = mapped_column(Integer, default=0)  # 리뷰가 받은 도움돼요 수
    is_best: Mapped[bool] = mapped_column(Boolean, default=False)  # 베스트 리뷰인지 여부
    is_blinded: Mapped[bool] = mapped_column(Boolean, default=False)  # 화면에서 가려진 리뷰인지 여부

    reply_content: Mapped[Optional[str]] = mapped_column(Text)  # 관리자 답변
    replied_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))  # 답변 작성 시각

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )  # 리뷰 작성 시각
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )  # 리뷰 생성 또는 수정 시각

    # 리뷰 작성자 정보를 조회할 때 회원 정보도 함께 가져온다.
    member: Mapped["object"] = relationship("Member", lazy="joined")

    # 리뷰가 달린 도서 정보를 함께 가져온다.
    book: Mapped["object"] = relationship("Book", lazy="joined")

    # 리뷰에 첨부된 사진 목록.
    # 리뷰가 삭제되면 사진 정보도 함께 삭제한다.
    images: Mapped[List["ReviewImage"]] = relationship(
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # 리뷰 하나에 감성 분석 결과 하나를 연결한다.
    # uselist=False는 관계가 여러 개가 아니라 하나라는 뜻이다.
    sentiment: Mapped[Optional["ReviewSentiment"]] = relationship(
        back_populates="review",
        uselist=False,
        cascade="all, delete-orphan",
    )


class ReviewImage(Base):
    """리뷰에 첨부된 사진 정보."""

    __tablename__ = "review_images"
    __table_args__ = {"schema": "shop"}

    image_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # 사진 정보 번호

    # 이 사진이 속한 리뷰. 리뷰가 삭제되면 사진 정보도 삭제한다.
    review_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("shop.reviews.review_id", ondelete="CASCADE"),
    )

    image_url: Mapped[str] = mapped_column(String(255), nullable=False)  # 사진 주소
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=0)  # 사진 표시 순서


class ReviewLike(Base):
    """회원이 리뷰에 누른 도움돼요 기록."""

    __tablename__ = "review_likes"
    __table_args__ = {"schema": "shop"}

    # 리뷰 번호와 회원 번호를 함께 기본 키로 사용한다.
    # 같은 회원이 같은 리뷰에 중복으로 좋아요를 기록하지 못하게 한다.
    review_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("shop.reviews.review_id", ondelete="CASCADE"),
        primary_key=True,
    )
    member_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("shop.members.member_id", ondelete="CASCADE"),
        primary_key=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )  # 도움돼요를 누른 시각


class ReviewSentiment(Base):
    """AI가 리뷰를 분석한 결과."""

    __tablename__ = "review_sentiments"
    __table_args__ = {"schema": "ai"}  # AI 분석 데이터는 ai 스키마에 저장

    sentiment_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # 분석 결과 번호

    # 리뷰 번호에 unique=True가 있어 리뷰 하나에 분석 결과 하나만 연결된다.
    # 리뷰가 삭제되면 분석 결과도 삭제한다.
    review_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("shop.reviews.review_id", ondelete="CASCADE"),
        unique=True,
    )

    book_id: Mapped[int] = mapped_column(BigInteger, nullable=False)  # 리뷰 대상 도서 번호

    # 감성 분석 결과를 긍정·중립·부정 중 하나로 저장한다.
    # Enum 타입 자체는 shop 스키마에 이미 만들어져 있다고 가정한다.
    label: Mapped[SentimentLabel] = mapped_column(
        PgEnum(
            SentimentLabel,
            name="sentiment_label",
            schema="shop",
            create_type=False,
        )
    )

    score: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)  # 모델이 계산한 대표 점수
    positive_prob: Mapped[float] = mapped_column(Numeric(6, 4), default=0)  # 긍정일 확률
    negative_prob: Mapped[float] = mapped_column(Numeric(6, 4), default=0)  # 부정일 확률
    keywords: Mapped[Optional[dict]] = mapped_column(JSONB)  # 분석에서 뽑은 주요 단어 등
    model_version: Mapped[str] = mapped_column(
        String(40),
        default="kosa-lr-v1",
    )  # 분석에 사용한 모델 버전

    analyzed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )  # 분석이 실행된 시각

    # 이 분석 결과가 어떤 리뷰에서 나왔는지 연결한다.
    review: Mapped["Review"] = relationship(back_populates="sentiment")