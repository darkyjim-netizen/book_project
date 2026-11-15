"""도서 API에서 주고받는 요청과 응답 데이터 형식."""
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CategoryResponse(BaseModel):
    """카테고리 정보와 그 아래 하위 카테고리 목록."""

    # SQLAlchemy 객체의 속성에서 응답 값을 읽을 수 있게 한다.
    model_config = ConfigDict(from_attributes=True)

    category_id: int  # 카테고리 번호
    parent_id: Optional[int] = None  # 상위 카테고리 번호. 최상위면 없음
    name: str  # 카테고리 이름
    full_path: str  # 전체 경로. 예: 도서 > 소설
    depth: int  # 카테고리 단계
    children: List["CategoryResponse"] = []  # 하위 카테고리. 같은 형식으로 재귀 구성


class PublisherResponse(BaseModel):
    """출판사 정보를 반환하는 형식."""

    model_config = ConfigDict(from_attributes=True)

    publisher_id: int  # 출판사 번호
    name: str  # 출판사명
    country_code: str  # 국가 코드


class AuthorResponse(BaseModel):
    """저자 정보를 반환하는 형식."""

    model_config = ConfigDict(from_attributes=True)

    author_id: int  # 저자 번호
    name: str  # 저자 이름
    name_original: Optional[str] = None  # 원어 이름. 없을 수 있음
    country_code: str  # 국가 코드


class BookListItem(BaseModel):
    """도서 목록이나 검색 결과에 필요한 간단한 정보."""

    book_id: int  # 도서 번호
    isbn13: str  # ISBN-13 국제 표준 도서 번호
    title: str  # 도서 제목
    subtitle: Optional[str] = None  # 부제목
    authors: List[str] = []  # 저자 이름 목록
    publisher: Optional[str] = None  # 출판사명
    category_name: Optional[str] = None  # 카테고리명

    list_price: float  # 정가
    sale_price: float  # 판매가
    discount_rate: float  # 할인율

    cover_image: Optional[str] = None  # 표지 이미지 주소
    status: str  # 판매 상태
    stock_qty: int  # 현재 재고
    rating_avg: float  # 평균 평점
    review_count: int  # 리뷰 수
    sales_count: int  # 판매 수량
    is_domestic: bool  # 국내 도서인지 여부
    published_date: Optional[date] = None  # 출간일


class BookDetailResponse(BookListItem):
    """도서 상세 페이지에 필요한 정보. 목록용 필드도 함께 포함한다."""

    translator: Optional[str] = None  # 번역자
    page_count: Optional[int] = None  # 페이지 수
    binding: Optional[str] = None  # 제본 형태
    size_mm: Optional[str] = None  # 책 크기
    weight_g: Optional[int] = None  # 무게(그램)
    language_code: str = "ko"  # 도서 언어 코드

    summary: Optional[str] = None  # 짧은 소개
    description: Optional[str] = None  # 상세 설명
    table_of_contents: Optional[str] = None  # 목차
    publisher_review: Optional[str] = None  # 출판사 서평

    point_rate: float = 1.0  # 구매 시 포인트 적립률
    view_count: int = 0  # 조회 수
    sentiment_score: Optional[float] = None  # 리뷰 감성 분석 점수
    images: List[str] = []  # 추가 이미지 주소 목록
    is_wished: bool = False  # 현재 회원의 위시리스트에 들어 있는지 여부


class BookCreateRequest(BaseModel):
    """관리자가 새 도서를 등록할 때 받을 데이터."""

    # ISBN-13은 정확히 13글자여야 한다.
    isbn13: str = Field(..., min_length=13, max_length=13)
    isbn10: Optional[str] = Field(None, max_length=10)  # ISBN-10. 없을 수 있음
    title: str = Field(..., max_length=300)  # 필수 도서 제목
    subtitle: Optional[str] = Field(None, max_length=300)  # 선택 부제목

    category_id: int  # 연결할 카테고리 번호
    publisher_id: int  # 연결할 출판사 번호
    author_ids: List[int] = []  # 연결할 저자 번호 목록
    translator: Optional[str] = None  # 번역자

    list_price: int = Field(..., ge=0)  # 정가. 0 이상이어야 함
    sale_price: int = Field(..., ge=0)  # 판매가. 0 이상이어야 함
    stock_qty: int = Field(0, ge=0)  # 재고 수량. 기본값 0
    safety_stock: int = Field(5, ge=0)  # 재고 부족 판단 기준. 기본값 5
    status: str = "SALE"  # 판매 상태
    is_domestic: bool = True  # 국내 도서 여부
    language_code: str = "ko"  # 기본 언어는 한국어
    published_date: Optional[date] = None  # 출간일
    page_count: Optional[int] = None  # 페이지 수
    binding: Optional[str] = None  # 제본 형태
    summary: Optional[str] = None  # 짧은 소개
    description: Optional[str] = None  # 상세 설명
    table_of_contents: Optional[str] = None  # 목차
    cover_image: Optional[str] = None  # 표지 이미지 주소

    @field_validator("isbn13")
    @classmethod
    def _isbn(cls, v: str):
        """ISBN-13에 숫자만 들어왔는지 확인한다."""

        # 글자 수 13자 검사는 위 Field 설정에서 먼저 수행한다.
        if not v.isdigit():
            raise ValueError("ISBN13 은 숫자 13자리여야 합니다.")
        return v


class BookUpdateRequest(BaseModel):
    """도서 정보를 수정할 때 받을 데이터.

    모든 항목이 선택값이므로, 보낸 필드만 골라 수정하는 데 사용할 수 있다.
    """

    title: Optional[str] = None
    subtitle: Optional[str] = None
    category_id: Optional[int] = None
    publisher_id: Optional[int] = None
    author_ids: Optional[List[int]] = None  # 저자 목록을 바꾸려면 새 번호 목록 전달
    list_price: Optional[int] = Field(None, ge=0)
    sale_price: Optional[int] = Field(None, ge=0)
    stock_qty: Optional[int] = Field(None, ge=0)
    safety_stock: Optional[int] = Field(None, ge=0)
    status: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    table_of_contents: Optional[str] = None
    cover_image: Optional[str] = None


class BookSearchParams(BaseModel):
    """도서 목록을 검색하거나 정렬할 때 사용할 조건."""

    keyword: Optional[str] = None  # 제목·저자 등의 검색어
    category_id: Optional[int] = None  # 카테고리로 필터링
    publisher_id: Optional[int] = None  # 출판사로 필터링
    author_id: Optional[int] = None  # 저자로 필터링
    min_price: Optional[int] = None  # 최저 가격
    max_price: Optional[int] = None  # 최고 가격
    is_domestic: Optional[bool] = None  # 국내 도서 여부로 필터링
    in_stock_only: bool = False  # True면 재고 있는 도서만 조회

    # 허용된 정렬 이름 중 하나만 입력할 수 있다.
    sort: str = Field(
        "recent",
        pattern="^(recent|sales|price_asc|price_desc|rating|review|title)$",
    )

    page: int = Field(1, ge=1)  # 조회할 페이지. 1부터 시작
    size: int = Field(20, ge=1, le=100)  # 페이지당 결과 수. 1~100 허용


class StockUpdateRequest(BaseModel):
    """도서 재고를 조정할 때 받을 데이터."""

    change_qty: int = Field(
        ...,
        description="증감 수량(음수 가능)",
    )  # 재고를 늘릴 때 양수, 줄일 때 음수
    reason: str = Field("ADMIN_ADJUST", max_length=40)  # 재고 변경 사유
    memo: Optional[str] = None  # 추가 메모


# CategoryResponse가 자기 자신을 children 타입으로 참조하므로
# 클래스 정의가 끝난 뒤 참조할 타입을 다시 확인한다.
CategoryResponse.model_rebuild()