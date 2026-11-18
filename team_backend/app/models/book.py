"""도서와 상품 정보를 저장하는 ORM 모델."""
from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import (
    BigInteger,  # 큰 정수
    Boolean,     # 참 또는 거짓
    CHAR,        # 정해진 길이의 문자열
    Date,        # 날짜
    DateTime,    # 날짜와 시각
    Enum as PgEnum,  # PostgreSQL ENUM
    ForeignKey,  # 다른 테이블의 열을 참조
    Integer,
    Numeric,     # 금액·비율처럼 소수 자릿수를 관리하는 숫자
    SmallInteger,
    String,      # 최대 길이가 정해진 문자열
    Text,        # 긴 문자열
    func,        # now() 같은 DB 함수
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from team_backend.app.core.database import Base  # 모든 ORM 모델의 공통 부모 클래스
from team_backend.app.models.enums import BookStatus  # 도서 판매 상태를 나타내는 Enum


class Category(Base):
    """도서 카테고리. parent_id로 상위·하위 카테고리를 표현한다."""

    __tablename__ = "categories"
    __table_args__ = {"schema": "shop"}  # shop 스키마의 테이블

    category_id: Mapped[int] = mapped_column(Integer, primary_key=True)  # 카테고리 번호

    # 상위 카테고리 번호. 최상위 카테고리라면 값이 없을 수 있다.
    # 자기 자신의 테이블인 categories를 참조한다.
    parent_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("shop.categories.category_id"),
    )

    name: Mapped[str] = mapped_column(String(80), nullable=False)  # 카테고리 이름
    full_path: Mapped[str] = mapped_column(String(255), nullable=False)  # 전체 경로, 예: 도서 > 소설
    depth: Mapped[int] = mapped_column(SmallInteger, default=1)  # 카테고리 단계
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=0)  # 화면 표시 순서
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)  # 현재 사용 중인지 여부
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )  # DB가 자동으로 기록하는 생성 시각

    # 이 카테고리 아래에 속한 하위 카테고리들
    children: Mapped[List["Category"]] = relationship(
        back_populates="parent",
        cascade="all",       # 부모 카테고리의 변경을 하위 관계에도 적용
        single_parent=True,  # 하위 카테고리는 한 부모에만 연결
    )

    # 이 카테고리의 상위 카테고리. 최상위 카테고리는 None일 수 있다.
    parent: Mapped[Optional["Category"]] = relationship(
        back_populates="children",
        remote_side=[category_id],  # 자기 참조 관계에서 부모 쪽 열을 지정
    )


class Publisher(Base):
    """출판사 정보를 저장하는 테이블."""

    __tablename__ = "publishers"
    __table_args__ = {"schema": "shop"}

    publisher_id: Mapped[int] = mapped_column(Integer, primary_key=True)  # 출판사 번호
    name: Mapped[str] = mapped_column(
        String(120),
        unique=True,     # 같은 출판사 이름은 중복 저장할 수 없다.
        nullable=False,  # 출판사 이름은 필수다.
    )
    country_code: Mapped[str] = mapped_column(CHAR(2), default="KR")  # 국가 코드 두 글자
    homepage: Mapped[Optional[str]] = mapped_column(String(255))  # 홈페이지 주소
    description: Mapped[Optional[str]] = mapped_column(Text)  # 출판사 설명
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class Author(Base):
    """저자 정보를 저장하는 테이블."""

    __tablename__ = "authors"
    __table_args__ = {"schema": "shop"}

    author_id: Mapped[int] = mapped_column(Integer, primary_key=True)  # 저자 번호
    name: Mapped[str] = mapped_column(String(120), nullable=False)  # 화면에 표시할 저자 이름
    name_original: Mapped[Optional[str]] = mapped_column(String(160))  # 원어 이름
    country_code: Mapped[str] = mapped_column(CHAR(2), default="KR")  # 국가 코드
    biography: Mapped[Optional[str]] = mapped_column(Text)  # 저자 소개
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class BookAuthor(Base):
    """도서와 저자의 연결 정보. 한 책에 저자가 여러 명일 수 있다."""

    __tablename__ = "book_authors"
    __table_args__ = {"schema": "shop"}

    # 도서 번호. 복합 기본 키의 일부이며 책이 삭제되면 연결 행도 삭제된다.
    book_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("shop.books.book_id", ondelete="CASCADE"),
        primary_key=True,
    )

    # 저자 번호. 복합 기본 키의 일부이며 저자가 삭제되면 연결 행도 삭제된다.
    author_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("shop.authors.author_id", ondelete="CASCADE"),
        primary_key=True,
    )

    # book_id, author_id, role을 함께 기본 키로 사용한다.
    # 저자가 저자이자 번역자처럼 서로 다른 역할로 연결될 수 있다.
    role: Mapped[str] = mapped_column(String(20), primary_key=True, default="AUTHOR")
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=0)  # 저자 표시 순서

    # 저자 정보를 조회할 때 저자 행도 함께 가져온다.
    author: Mapped["Author"] = relationship(lazy="joined")

    # 연결된 도서. Book.book_authors와 양방향으로 연결된다.
    book: Mapped["Book"] = relationship(back_populates="book_authors")


class BookImage(Base):
    """도서의 표지나 상세 이미지 정보를 저장하는 테이블."""

    __tablename__ = "book_images"
    __table_args__ = {"schema": "shop"}

    image_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # 이미지 번호

    # 이미지가 속한 도서 번호. 도서가 삭제되면 이미지 정보도 삭제된다.
    book_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("shop.books.book_id", ondelete="CASCADE"),
    )

    image_url: Mapped[str] = mapped_column(String(255), nullable=False)  # 이미지 주소
    image_type: Mapped[str] = mapped_column(String(20), default="DETAIL")  # 이미지 종류
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=0)  # 이미지 표시 순서


class Book(Base):
    """도서 상품의 기본 정보와 판매 정보를 저장하는 테이블."""

    __tablename__ = "books"
    __table_args__ = {"schema": "shop"}

    book_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # 도서 번호
    isbn13: Mapped[str] = mapped_column(
        String(13),
        unique=True,     # ISBN-13은 중복될 수 없다.
        nullable=False,  # ISBN-13은 필수다.
    )
    isbn10: Mapped[Optional[str]] = mapped_column(String(10))  # ISBN-10이 있는 경우 저장
    title: Mapped[str] = mapped_column(String(300), nullable=False)  # 도서 제목
    subtitle: Mapped[Optional[str]] = mapped_column(String(300))  # 부제목
    title_original: Mapped[Optional[str]] = mapped_column(String(300))  # 원어 제목

    # 도서가 속한 카테고리와 출판사 번호
    category_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("shop.categories.category_id"),
    )
    publisher_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("shop.publishers.publisher_id"),
    )

    translator: Mapped[Optional[str]] = mapped_column(String(200))  # 번역자 이름

    # 판매 가격과 정가. Numeric은 금액처럼 정확도가 필요한 숫자에 적합하다.
    list_price: Mapped[float] = mapped_column(Numeric(10, 0), nullable=False)
    sale_price: Mapped[float] = mapped_column(Numeric(10, 0), nullable=False)
    discount_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=0)  # 할인율
    point_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=1.0)  # 포인트 적립률

    stock_qty: Mapped[int] = mapped_column(Integer, default=0)  # 현재 재고 수량
    safety_stock: Mapped[int] = mapped_column(Integer, default=5)  # 재고 부족 판단 기준

    # DB에 미리 정의한 book_status ENUM 타입을 사용한다.
    status: Mapped[BookStatus] = mapped_column(
        PgEnum(BookStatus, name="book_status", schema="shop", create_type=False),
        default=BookStatus.SALE,
    )

    is_domestic: Mapped[bool] = mapped_column(Boolean, default=True)  # 국내 도서인지 여부
    language_code: Mapped[str] = mapped_column(CHAR(2), default="ko")  # 도서 언어 코드
    published_date: Mapped[Optional[date]] = mapped_column(Date)  # 출간일
    page_count: Mapped[Optional[int]] = mapped_column(Integer)  # 페이지 수
    weight_g: Mapped[Optional[int]] = mapped_column(Integer)  # 무게(그램)
    size_mm: Mapped[Optional[str]] = mapped_column(String(40))  # 책 크기
    binding: Mapped[Optional[str]] = mapped_column(String(40))  # 제본 형태
    edition: Mapped[Optional[str]] = mapped_column(String(40))  # 판 또는 에디션 정보

    summary: Mapped[Optional[str]] = mapped_column(Text)  # 짧은 소개
    description: Mapped[Optional[str]] = mapped_column(Text)  # 상세 설명
    table_of_contents: Mapped[Optional[str]] = mapped_column(Text)  # 목차
    publisher_review: Mapped[Optional[str]] = mapped_column(Text)  # 출판사 서평

    cover_image: Mapped[Optional[str]] = mapped_column(String(255))  # 대표 표지 이미지 주소
    is_ebook_available: Mapped[bool] = mapped_column(Boolean, default=False)  # 전자책 제공 여부
    is_gift_wrap: Mapped[bool] = mapped_column(Boolean, default=True)  # 선물 포장 가능 여부

    view_count: Mapped[int] = mapped_column(Integer, default=0)  # 조회 수
    sales_count: Mapped[int] = mapped_column(Integer, default=0)  # 판매 수량
    review_count: Mapped[int] = mapped_column(Integer, default=0)  # 리뷰 수
    rating_avg: Mapped[float] = mapped_column(Numeric(3, 2), default=0)  # 평균 평점
    sentiment_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))  # AI 감성 분석 점수

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # 도서의 카테고리 정보를 함께 가져온다.
    category: Mapped["Category"] = relationship(lazy="joined")

    # 도서의 출판사 정보를 함께 가져온다.
    publisher: Mapped["Publisher"] = relationship(lazy="joined")

    # 도서와 저자의 연결 목록.
    # 도서에서 저자 연결을 제거하면 연결 테이블 행도 삭제한다.
    book_authors: Mapped[List["BookAuthor"]] = relationship(
        back_populates="book",
        cascade="all, delete-orphan",
    )

    # 도서에 연결된 이미지 목록.
    # primaryjoin은 도서 번호를 기준으로 이미지 테이블과 연결하라는 뜻이다.
    images: Mapped[List["BookImage"]] = relationship(
        cascade="all, delete-orphan",
        primaryjoin="Book.book_id == BookImage.book_id",
    )

    # ------------------------------------------------------------------ helper
    @property
    def author_names(self) -> List[str]:
        """저자 이름들을 표시 순서대로 모아 돌려준다."""
        return [
            ba.author.name
            for ba in sorted(self.book_authors, key=lambda x: x.sort_order)
        ]

    @property
    def author_display(self) -> str:
        """저자 수에 맞춰 화면에 표시할 문구를 만든다."""
        names = self.author_names

        if not names:
            return "저자 미상"  # 저자 정보가 없을 때

        if len(names) == 1:
            return names[0]  # 저자가 한 명일 때

        # 저자가 여러 명이면 첫 번째 저자와 나머지 인원 수를 표시한다.
        return f"{names[0]} 외 {len(names) - 1}명"

    @property
    def is_available(self) -> bool:
        """판매 중이고 재고가 있으면 구매 가능으로 판단한다."""
        return self.status == BookStatus.SALE and self.stock_qty > 0

    @property
    def is_low_stock(self) -> bool:
        """재고가 안전 재고 기준 이하인지 확인한다."""
        return self.stock_qty <= self.safety_stock

    def __repr__(self) -> str:  # pragma: no cover
        """개발 중 객체를 출력할 때 식별하기 쉬운 문자열을 만든다."""
        return f"<Book {self.book_id} {self.title[:20]}>"


class StockHistory(Base):
    """재고가 바뀐 기록을 저장하는 로그 테이블."""

    __tablename__ = "stock_histories"
    __table_args__ = {"schema": "log"}

    history_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # 기록 번호
    book_id: Mapped[int] = mapped_column(BigInteger, nullable=False)  # 재고가 바뀐 도서 번호
    change_qty: Mapped[int] = mapped_column(Integer, nullable=False)  # 변동 수량
    after_qty: Mapped[int] = mapped_column(Integer, nullable=False)  # 변동 후 재고
    reason: Mapped[str] = mapped_column(String(40), nullable=False)  # 변경 사유
    ref_id: Mapped[Optional[int]] = mapped_column(BigInteger)  # 관련 주문 등의 번호
    created_by: Mapped[Optional[int]] = mapped_column(BigInteger)  # 변경한 사용자 번호
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class RecentView(Base):
    """회원이나 방문자가 최근 본 도서 기록을 저장하는 로그 테이블."""

    __tablename__ = "recent_views"
    __table_args__ = {"schema": "log"}

    view_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # 조회 기록 번호
    member_id: Mapped[Optional[int]] = mapped_column(BigInteger)  # 로그인 회원이면 회원 번호
    session_key: Mapped[Optional[str]] = mapped_column(String(64))  # 비회원 방문자를 구분하는 세션 키
    book_id: Mapped[int] = mapped_column(BigInteger, nullable=False)  # 조회한 도서 번호
    dwell_seconds: Mapped[int] = mapped_column(Integer, default=0)  # 도서 페이지에 머문 시간(초)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class SearchLog(Base):
    """도서 검색 기록을 저장하는 로그 테이블."""

    __tablename__ = "search_logs"
    __table_args__ = {"schema": "log"}

    search_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # 검색 기록 번호
    member_id: Mapped[Optional[int]] = mapped_column(BigInteger)  # 로그인 회원이면 회원 번호
    keyword: Mapped[str] = mapped_column(String(200), nullable=False)  # 검색어
    result_count: Mapped[int] = mapped_column(Integer, default=0)  # 검색 결과 수
    clicked_book_id: Mapped[Optional[int]] = mapped_column(BigInteger)  # 검색 후 클릭한 도서 번호
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )