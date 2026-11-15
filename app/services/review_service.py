"""리뷰 서비스. 리뷰 작성 시 감성분석도 수행한다."""
import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import BusinessError, NotFoundError
from app.models.book import Book
from app.models.enums import OrderStatus, PointReason, SentimentLabel
from app.models.member import Member, PointHistory
from app.models.order import OrderItem
from app.models.review import Review, ReviewImage, ReviewLike, ReviewSentiment
from app.schemas.review import (
    ReviewCreateRequest,
    ReviewResponse,
    ReviewStatsResponse,
    ReviewUpdateRequest,
    SentimentResponse,
)

logger = logging.getLogger(__name__)

# 글만 있는 리뷰를 작성했을 때 지급할 포인트
TEXT_REVIEW_POINT = 300

# 사진을 포함한 리뷰를 작성했을 때 지급할 포인트
PHOTO_REVIEW_POINT = 1000


class ReviewService:
    """리뷰 작성, 조회, 수정, 삭제와 관련된 작업을 처리한다."""

    def __init__(self, db: Session):
        # 이 서비스에서 사용할 DB 세션
        self.db = db

    # ------------------------------------------------------------------ 응답 변환
    def to_response(
        self,
        review: Review,
        member_id: Optional[int] = None,
    ) -> ReviewResponse:
        """리뷰 DB 객체를 API 응답 형식으로 바꾼다."""

        # 로그인 회원이 이 리뷰에 '도움돼요'를 눌렀는지 확인한다.
        is_liked = False
        if member_id:
            like_count = (
                self.db.scalar(
                    select(func.count())
                    .select_from(ReviewLike)
                    .where(
                        ReviewLike.review_id == review.review_id,
                        ReviewLike.member_id == member_id,
                    )
                )
                or 0
            )
            is_liked = like_count > 0

        # 감성분석 결과가 있으면 응답 스키마 형태로 변환한다.
        sentiment = None
        if review.sentiment:
            sentiment = SentimentResponse(
                label=review.sentiment.label.value,
                score=float(review.sentiment.score),
                positive_prob=float(review.sentiment.positive_prob),
                negative_prob=float(review.sentiment.negative_prob),
                keywords=review.sentiment.keywords,
                model_version=review.sentiment.model_version,
            )

        # 리뷰 작성자의 닉네임을 우선 사용하고, 없으면 이름을 사용한다.
        # 회원 정보가 없으면 기본 표시 이름으로 '회원'을 쓴다.
        member_name = (
            review.member.nickname or review.member.name
            if review.member
            else "회원"
        )

        # 이름 가운데 글자를 별표로 가려 개인정보 노출을 줄인다.
        if len(member_name) > 2:
            member_name = (
                member_name[0]
                + "*" * (len(member_name) - 2)
                + member_name[-1]
            )

        # 리뷰 정보와 이미지, 답글, 감성분석 결과를 응답 객체에 담는다.
        return ReviewResponse(
            review_id=review.review_id,
            book_id=review.book_id,
            book_title=review.book.title if review.book else None,
            cover_image=review.book.cover_image if review.book else None,
            member_id=review.member_id,
            member_name=member_name,
            rating=review.rating,
            title=review.title,
            content=review.content,
            like_count=review.like_count,
            is_best=review.is_best,
            is_liked=is_liked,
            # 이미지 순서를 sort_order 기준으로 정렬해 URL 목록으로 만든다.
            images=[
                image.image_url
                for image in sorted(
                    review.images,
                    key=lambda image: image.sort_order,
                )
            ],
            reply_content=review.reply_content,
            replied_at=review.replied_at,
            sentiment=sentiment,
            created_at=review.created_at,
        )

    # ------------------------------------------------------------------ 리뷰 작성
    def create_review(
        self,
        member: Member,
        payload: ReviewCreateRequest,
    ) -> Review:
        """리뷰를 작성하고 감성분석과 포인트 적립을 수행한다."""

        # 리뷰 대상 도서가 실제로 있는지 확인한다.
        book = self.db.get(Book, payload.book_id)
        if book is None:
            raise NotFoundError("도서를 찾을 수 없습니다.")

        # 한 회원이 같은 도서에 리뷰를 두 번 작성하지 못하게 한다.
        exists = self.db.scalar(
            select(Review).where(
                Review.book_id == payload.book_id,
                Review.member_id == member.member_id,
            )
        )
        if exists:
            raise BusinessError(
                "이미 이 도서에 리뷰를 작성하셨습니다.",
                code="REVIEW_DUPLICATED",
            )

        order_item = None

        # 주문 상품 번호가 전달되었다면 실제 구매 내역과 리뷰 가능 여부를 확인한다.
        if payload.order_item_id:
            order_item = self.db.get(OrderItem, payload.order_item_id)

            # 주문 상품이 없거나, 리뷰 대상 도서와 주문 상품의 도서가 다르면 거부한다.
            if order_item is None or order_item.book_id != payload.book_id:
                raise BusinessError("주문 상품 정보가 올바르지 않습니다.")

            # 배송 완료 또는 구매 확정된 상품만 리뷰를 쓸 수 있다.
            if order_item.status not in (
                OrderStatus.DELIVERED,
                OrderStatus.CONFIRMED,
            ):
                raise BusinessError(
                    "배송 완료된 상품만 리뷰를 작성할 수 있습니다."
                )

            # 주문 상품 하나에 리뷰를 이미 작성했는지 확인한다.
            if order_item.is_reviewed:
                raise BusinessError("이미 리뷰를 작성한 주문 상품입니다.")

        # 리뷰 DB 객체를 만든다.
        review = Review(
            book_id=payload.book_id,
            member_id=member.member_id,
            order_item_id=payload.order_item_id,
            rating=payload.rating,
            title=payload.title,
            content=payload.content,
        )
        self.db.add(review)

        # 아직 전체 커밋은 하지 않지만 review_id를 먼저 확보한다.
        self.db.flush()

        # 리뷰 이미지 URL을 최대 5개까지 저장한다.
        for idx, url in enumerate(payload.image_urls[:5]):
            self.db.add(
                ReviewImage(
                    review_id=review.review_id,
                    image_url=url,
                    sort_order=idx,
                )
            )

        # 주문 상품을 통해 작성한 리뷰라면 해당 상품을 리뷰 작성 완료로 표시한다.
        if order_item is not None:
            order_item.is_reviewed = True

        # 리뷰 내용을 분석해 긍정·부정 등 감성 결과를 저장한다.
        self._analyze_and_save(review)

        # 사진이 있으면 사진 리뷰 포인트, 없으면 일반 리뷰 포인트를 준다.
        point = (
            PHOTO_REVIEW_POINT
            if payload.image_urls
            else TEXT_REVIEW_POINT
        )
        member.point_balance += point

        # 포인트 잔액 변경 내역을 저장한다.
        self.db.add(
            PointHistory(
                member_id=member.member_id,
                reason=PointReason.REVIEW,
                amount=point,
                balance_after=member.point_balance,
                ref_id=review.review_id,
                memo="리뷰 작성 적립",
            )
        )

        # 리뷰, 이미지, 감성분석, 포인트 변경 내역을 함께 저장한다.
        self.db.commit()
        self.db.refresh(review)

        # 이 도서의 감성 점수 평균도 다시 계산한다.
        self.refresh_book_sentiment(payload.book_id)

        logger.info(
            "리뷰 작성: review_id=%s book_id=%s",
            review.review_id,
            review.book_id,
        )
        return review

    def _analyze_and_save(self, review: Review) -> None:
        """리뷰 내용을 감성분석하고 결과를 DB에 저장한다."""

        # 감성분석 기능은 실제 사용할 때 이 함수 안에서 불러온다.
        # 리뷰 기능을 사용하지 않을 때 AI 모듈을 미리 불러오지 않아도 된다.
        from app.ai.sentiment import get_analyzer

        analyzer = get_analyzer()
        result = analyzer.analyze(review.content)

        # 분석 결과의 감성, 점수, 키워드, 모델 버전을 저장한다.
        self.db.add(
            ReviewSentiment(
                review_id=review.review_id,
                book_id=review.book_id,
                label=SentimentLabel(result["label"]),
                score=result["score"],
                positive_prob=result["positive_prob"],
                negative_prob=result["negative_prob"],
                keywords={
                    "positive": result["positive_keywords"],
                    "negative": result["negative_keywords"],
                },
                model_version=result["model_version"],
            )
        )

    def refresh_book_sentiment(
        self,
        book_id: int,
    ) -> Optional[float]:
        """도서에 작성된 리뷰의 감성 점수 평균을 갱신한다."""

        # 해당 도서에 저장된 감성분석 점수의 평균을 계산한다.
        avg = self.db.scalar(
            select(func.avg(ReviewSentiment.score)).where(
                ReviewSentiment.book_id == book_id
            )
        )

        book = self.db.get(Book, book_id)

        # 도서가 있으면 평균 점수를 저장한다.
        # 분석 결과가 하나도 없으면 점수를 None으로 비운다.
        if book is not None:
            book.sentiment_score = float(avg) if avg is not None else None
            self.db.commit()

        return float(avg) if avg is not None else None

    def update_review(
        self,
        review_id: int,
        member: Member,
        payload: ReviewUpdateRequest,
    ) -> Review:
        """리뷰를 수정한다. 내용이 바뀌면 감성분석도 다시 한다."""

        review = self.db.get(Review, review_id)
        if review is None:
            raise NotFoundError("리뷰를 찾을 수 없습니다.")

        # 작성자 본인이나 관리자만 수정할 수 있다.
        if review.member_id != member.member_id and not member.is_admin:
            raise BusinessError(
                "본인의 리뷰만 수정할 수 있습니다.",
                status_code=403,
            )

        # 요청에서 실제로 전달된 필드만 딕셔너리로 가져온다.
        data = payload.model_dump(exclude_unset=True)

        # content가 요청에 있고 기존 내용과 다를 때만 감성분석을 다시 한다.
        content_changed = (
            "content" in data
            and data["content"] != review.content
        )

        # 요청받은 필드만 리뷰 객체에 반영한다.
        for key, value in data.items():
            setattr(review, key, value)

        if content_changed:
            # 기존 분석 결과를 지우고 새 내용으로 다시 분석한다.
            self.db.query(ReviewSentiment).filter(
                ReviewSentiment.review_id == review_id
            ).delete(synchronize_session=False)

            self.db.flush()
            self._analyze_and_save(review)

        self.db.commit()
        self.db.refresh(review)

        # 내용이 바뀌었다면 도서의 감성 점수 평균도 다시 계산한다.
        if content_changed:
            self.refresh_book_sentiment(review.book_id)

        return review

    def delete_review(
        self,
        review_id: int,
        member: Member,
    ) -> None:
        """리뷰를 삭제하고 해당 도서의 감성 점수를 다시 계산한다."""

        review = self.db.get(Review, review_id)
        if review is None:
            raise NotFoundError("리뷰를 찾을 수 없습니다.")

        # 작성자 본인이나 관리자만 삭제할 수 있다.
        if review.member_id != member.member_id and not member.is_admin:
            raise BusinessError(
                "본인의 리뷰만 삭제할 수 있습니다.",
                status_code=403,
            )

        # 리뷰 삭제 후 감성 점수를 다시 계산할 수 있도록 도서 번호를 기억한다.
        book_id = review.book_id

        self.db.delete(review)
        self.db.commit()

        self.refresh_book_sentiment(book_id)

    # ------------------------------------------------------------------ 리뷰 조회
    def list_by_book(
        self,
        book_id: int,
        page: int = 1,
        size: int = 10,
        sort: str = "recent",
        sentiment: Optional[str] = None,
        rating: Optional[int] = None,
        member_id: Optional[int] = None,
    ) -> Tuple[List[ReviewResponse], int]:
        """도서의 리뷰를 조건에 따라 조회하고 전체 건수도 반환한다."""

        # 블라인드 처리되지 않은 해당 도서의 리뷰만 조회한다.
        conditions = [
            Review.book_id == book_id,
            Review.is_blinded == False,  # noqa: E712
        ]

        # 별점 필터가 전달되면 해당 별점의 리뷰만 남긴다.
        if rating:
            conditions.append(Review.rating == rating)

        # 응답을 만들 때 필요한 이미지, 감성, 회원, 도서 정보도 함께 불러온다.
        stmt = (
            select(Review)
            .options(
                selectinload(Review.images),
                selectinload(Review.sentiment),
                selectinload(Review.member),
                selectinload(Review.book),
            )
            .where(*conditions)
        )

        # 감성 필터가 있으면 감성분석 결과와 연결해 해당 감성만 조회한다.
        if sentiment:
            stmt = stmt.join(
                ReviewSentiment,
                ReviewSentiment.review_id == Review.review_id,
            ).where(
                ReviewSentiment.label == SentimentLabel(sentiment)
            )

        # 페이지 수를 계산하려고 조건에 맞는 전체 리뷰 개수를 구한다.
        count_stmt = (
            select(func.count())
            .select_from(Review)
            .where(*conditions)
        )

        # 감성 필터를 쓸 때는 건수 계산에도 같은 필터를 적용한다.
        if sentiment:
            count_stmt = count_stmt.join(
                ReviewSentiment,
                ReviewSentiment.review_id == Review.review_id,
            ).where(
                ReviewSentiment.label == SentimentLabel(sentiment)
            )

        total = self.db.scalar(count_stmt) or 0

        # 정렬 이름과 실제 DB 정렬 기준을 연결한다.
        order_map = {
            "recent": Review.created_at.desc(),
            "rating_desc": Review.rating.desc(),
            "rating_asc": Review.rating.asc(),
            "like": Review.like_count.desc(),
        }

        # 알 수 없는 정렬 값이 오면 최신순을 사용한다.
        stmt = stmt.order_by(
            order_map.get(sort, Review.created_at.desc())
        )

        # 요청한 페이지에 해당하는 리뷰만 가져온다.
        stmt = stmt.offset((page - 1) * size).limit(size)

        rows = list(self.db.scalars(stmt).unique())

        # 리뷰 객체들을 응답 형식으로 바꾸고 전체 개수와 함께 반환한다.
        return [
            self.to_response(review, member_id)
            for review in rows
        ], total

    def list_by_member(
        self,
        member: Member,
        page: int = 1,
        size: int = 10,
    ):
        """회원이 작성한 리뷰를 페이지 단위로 조회한다."""

        # 페이지와 관계없이 해당 회원의 전체 리뷰 수를 구한다.
        total = (
            self.db.scalar(
                select(func.count())
                .select_from(Review)
                .where(Review.member_id == member.member_id)
            )
            or 0
        )

        # 응답에 필요한 관련 데이터와 함께 최신 리뷰부터 조회한다.
        rows = list(
            self.db.scalars(
                select(Review)
                .options(
                    selectinload(Review.images),
                    selectinload(Review.sentiment),
                    selectinload(Review.member),
                    selectinload(Review.book),
                )
                .where(Review.member_id == member.member_id)
                .order_by(Review.created_at.desc())
                .offset((page - 1) * size)
                .limit(size)
            ).unique()
        )

        return [
            self.to_response(review, member.member_id)
            for review in rows
        ], total

    def reviewable_items(
        self,
        member: Member,
        limit: int = 20,
    ):
        """회원이 리뷰를 작성할 수 있는 주문 상품을 조회한다."""

        # 주문과 연결해 회원의 구매 상품인지 확인한다.
        from app.models.order import Order

        return list(
            self.db.scalars(
                select(OrderItem)
                .options(selectinload(OrderItem.book))
                .join(
                    Order,
                    Order.order_id == OrderItem.order_id,
                )
                .where(
                    Order.member_id == member.member_id,
                    OrderItem.is_reviewed == False,  # noqa: E712
                    OrderItem.status.in_(
                        [
                            OrderStatus.DELIVERED,
                            OrderStatus.CONFIRMED,
                        ]
                    ),
                )
                .order_by(OrderItem.created_at.desc())
                .limit(limit)
            ).unique()
        )

    # ------------------------------------------------------------------ 리뷰 통계
    def book_stats(self, book_id: int) -> ReviewStatsResponse:
        """도서의 별점 분포, 감성 비율, 주요 키워드를 집계한다."""

        book = self.db.get(Book, book_id)
        if book is None:
            raise NotFoundError("도서를 찾을 수 없습니다.")

        # 블라인드되지 않은 리뷰를 별점별로 세어 온다.
        dist_rows = self.db.execute(
            select(
                Review.rating,
                func.count(),
            )
            .where(
                Review.book_id == book_id,
                Review.is_blinded == False,  # noqa: E712
            )
            .group_by(Review.rating)
        ).all()

        # 별점 1~5점이 모두 응답에 나오도록 우선 0으로 초기화한다.
        distribution = {
            str(rating): 0
            for rating in range(1, 6)
        }

        # DB에서 집계한 별점별 건수로 초기값을 갱신한다.
        for rating, count in dist_rows:
            distribution[str(rating)] = count

        # 감성 라벨별 리뷰 수를 센다.
        sent_rows = self.db.execute(
            select(
                ReviewSentiment.label,
                func.count(),
            )
            .where(ReviewSentiment.book_id == book_id)
            .group_by(ReviewSentiment.label)
        ).all()

        # 감성 라벨을 키로 하고 개수를 값으로 하는 딕셔너리를 만든다.
        sent_map = {
            row[0].value: row[1]
            for row in sent_rows
        }

        # 리뷰 감성분석 결과에 들어 있는 긍정·부정 키워드를 모은다.
        pos_keywords, neg_keywords = self._aggregate_keywords(book_id)

        return ReviewStatsResponse(
            book_id=book_id,
            review_count=book.review_count,
            rating_avg=float(book.rating_avg),
            rating_distribution=distribution,
            positive_count=sent_map.get("POSITIVE", 0),
            neutral_count=sent_map.get("NEUTRAL", 0),
            negative_count=sent_map.get("NEGATIVE", 0),
            sentiment_score=(
                float(book.sentiment_score)
                if book.sentiment_score
                else None
            ),
            positive_keywords=pos_keywords,
            negative_keywords=neg_keywords,
        )

    def _aggregate_keywords(
        self,
        book_id: int,
        top_n: int = 8,
    ):
        """도서 리뷰에 나온 긍정·부정 키워드를 빈도순으로 뽑는다."""

        from collections import Counter

        # 해당 도서의 감성분석 키워드 데이터를 가져온다.
        rows = self.db.scalars(
            select(ReviewSentiment.keywords).where(
                ReviewSentiment.book_id == book_id
            )
        ).all()

        # Counter는 단어가 나온 횟수를 세는 데 사용한다.
        pos = Counter()
        neg = Counter()

        for keywords in rows:
            if not keywords:
                continue

            pos.update(keywords.get("positive") or [])
            neg.update(keywords.get("negative") or [])

        # 가장 많이 나온 긍정·부정 키워드를 각각 top_n개 반환한다.
        return (
            [word for word, _ in pos.most_common(top_n)],
            [word for word, _ in neg.most_common(top_n)],
        )

    # ------------------------------------------------------------------ 기타 기능
    def toggle_like(
        self,
        review_id: int,
        member: Member,
    ) -> bool:
        """리뷰의 '도움돼요' 상태를 켜거나 끈다."""

        review = self.db.get(Review, review_id)
        if review is None:
            raise NotFoundError("리뷰를 찾을 수 없습니다.")

        # 이 회원이 해당 리뷰에 이미 좋아요를 눌렀는지 확인한다.
        existing = self.db.scalar(
            select(ReviewLike).where(
                ReviewLike.review_id == review_id,
                ReviewLike.member_id == member.member_id,
            )
        )

        if existing:
            # 이미 눌렀다면 취소하고 좋아요 수를 1 줄인다.
            self.db.delete(existing)
            review.like_count = max(review.like_count - 1, 0)
            self.db.commit()
            return False

        # 아직 누르지 않았다면 좋아요 기록을 만들고 수를 1 늘린다.
        self.db.add(
            ReviewLike(
                review_id=review_id,
                member_id=member.member_id,
            )
        )
        review.like_count += 1
        self.db.commit()

        return True

    def reply(
        self,
        review_id: int,
        content: str,
    ) -> Review:
        """리뷰에 관리자 답글을 등록한다."""

        review = self.db.get(Review, review_id)
        if review is None:
            raise NotFoundError("리뷰를 찾을 수 없습니다.")

        review.reply_content = content
        review.replied_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(review)

        return review

    def set_blind(
        self,
        review_id: int,
        blinded: bool,
    ) -> Review:
        """리뷰를 블라인드하거나 블라인드를 해제한다."""

        review = self.db.get(Review, review_id)
        if review is None:
            raise NotFoundError("리뷰를 찾을 수 없습니다.")

        # True면 블라인드, False면 블라인드 해제 상태가 된다.
        review.is_blinded = blinded

        self.db.commit()
        self.db.refresh(review)

        return review

    def mark_best_reviews(
        self,
        top_n: int = 20,
    ) -> int:
        """도움돼요 수가 많은 리뷰를 베스트 리뷰로 지정한다."""

        # 먼저 기존 베스트 리뷰 표시를 전부 해제한다.
        self.db.query(Review).filter(
            Review.is_best == True  # noqa: E712
        ).update(
            {Review.is_best: False},
            synchronize_session=False,
        )

        # 블라인드되지 않은 리뷰를 도움돼요 수가 많은 순으로 정렬해
        # 상위 top_n개를 베스트 리뷰로 지정한다.
        sql = text(
            """
            UPDATE shop.reviews SET is_best = true
             WHERE review_id IN (
                   SELECT review_id FROM shop.reviews
                    WHERE is_blinded = false
                    ORDER BY like_count DESC, created_at DESC
                    LIMIT :lim)
            """
        )

        self.db.execute(sql, {"lim": top_n})
        self.db.commit()

        # 이 함수는 지정 요청한 베스트 리뷰 수를 반환한다.
        return top_n