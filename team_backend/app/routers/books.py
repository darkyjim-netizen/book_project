"""도서 조회와 리뷰, 추천 관련 API 라우터."""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from team_backend.app.core.database import get_db  # 요청에서 사용할 DB 세션 제공
from team_backend.app.core.security import get_current_member_optional  # 로그인 여부와 관계없이 회원 정보 조회
from team_backend.app.schemas.book import (
    BookDetailResponse,
    BookListItem,
    BookSearchParams,
    CategoryResponse,
)
from team_backend.app.schemas.common import PageMeta, PageResponse
from team_backend.app.schemas.review import ReviewResponse, ReviewStatsResponse
from team_backend.app.services.book_service import BookService
from team_backend.app.services.review_service import ReviewService

# 이 라우터의 주소 앞에는 /books가 붙고 API 문서에는 "도서" 그룹으로 표시된다.
router = APIRouter(prefix="/books", tags=["도서"])


@router.get(
    "",
    response_model=PageResponse[BookListItem],
    summary="도서 목록/검색",
)
def list_books(
    keyword: Optional[str] = Query(None, description="제목/저자/ISBN 검색어"),
    category_id: Optional[int] = Query(None, description="카테고리 ID(하위 포함)"),
    publisher_id: Optional[int] = None,  # 출판사로 검색할 때 사용할 번호
    author_id: Optional[int] = None,  # 저자로 검색할 때 사용할 번호
    min_price: Optional[int] = None,  # 최저 판매가
    max_price: Optional[int] = None,  # 최고 판매가
    is_domestic: Optional[bool] = None,  # 국내 도서 여부
    in_stock_only: bool = False,  # True면 재고 있는 도서만 검색
    sort: str = Query(
        "recent",
        description="recent|sales|price_asc|price_desc|rating|review|title",
    ),
    page: int = Query(1, ge=1),  # 페이지 번호는 1부터 시작
    size: int = Query(20, ge=1, le=100),  # 페이지당 결과 수는 1~100
    db: Session = Depends(get_db),
    member=Depends(get_current_member_optional),  # 비회원 검색도 허용한다.
):
    """검색 조건에 맞는 도서를 페이지 단위로 조회한다."""

    # URL 쿼리값을 하나의 검색 조건 객체로 묶는다.
    params = BookSearchParams(
        keyword=keyword,
        category_id=category_id,
        publisher_id=publisher_id,
        author_id=author_id,
        min_price=min_price,
        max_price=max_price,
        is_domestic=is_domestic,
        in_stock_only=in_stock_only,
        sort=sort,
        page=page,
        size=size,
    )

    # 검색 결과와 전체 결과 수를 가져온다.
    # 로그인 회원이면 검색 기록에 회원 번호도 저장할 수 있다.
    items, total = BookService(db).search(
        params,
        member.member_id if member else None,
    )

    # 항목 목록과 페이지 정보를 함께 반환한다.
    return PageResponse[BookListItem](
        items=items,
        meta=PageMeta.build(page, size, total),
    )


@router.get(
    "/categories",
    response_model=List[dict],
    summary="카테고리 트리",
)
def categories(db: Session = Depends(get_db)):
    """전체 카테고리를 부모-자식 계층 구조로 반환한다."""
    return BookService(db).category_tree()


@router.get(
    "/bestsellers",
    response_model=List[BookListItem],
    summary="베스트셀러",
)
def bestsellers(
    limit: int = Query(10, ge=1, le=50),  # 가져올 도서 수
    category_id: Optional[int] = None,  # 지정하면 해당 카테고리 내에서 검색
    db: Session = Depends(get_db),
):
    """판매량 기준 베스트셀러를 반환한다."""
    return BookService(db).list_bestsellers(limit, category_id)


@router.get(
    "/new-releases",
    response_model=List[BookListItem],
    summary="신간 목록",
)
def new_releases(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """출간일 기준 신간 도서를 반환한다."""
    return BookService(db).list_new_releases(limit)


@router.get(
    "/popular-keywords",
    response_model=List[dict],
    summary="인기 검색어",
)
def popular_keywords(
    limit: int = Query(10, ge=1, le=30),
    db: Session = Depends(get_db),
):
    """최근 7일 동안 많이 검색된 단어를 반환한다."""
    return BookService(db).popular_keywords(limit)


@router.get(
    "/recent-views",
    response_model=List[BookListItem],
    summary="최근 본 도서",
)
def recent_views(
    limit: int = Query(10, ge=1, le=30),
    db: Session = Depends(get_db),
    member=Depends(get_current_member_optional),
):
    """로그인 회원이 최근 본 도서를 반환한다."""

    # 로그인하지 않은 사용자는 회원별 조회 이력을 가져올 수 없다.
    if member is None:
        return []

    return BookService(db).list_recent_views(member.member_id, limit)


@router.get(
    "/{book_id}",
    response_model=BookDetailResponse,
    summary="도서 상세",
)
def get_book(
    book_id: int,  # 조회할 도서 번호
    request: Request,  # 요청 쿠키에서 비회원 세션을 확인할 때 사용
    db: Session = Depends(get_db),
    member=Depends(get_current_member_optional),
):
    """도서 상세 정보를 반환하고 조회 기록을 남긴다."""

    service = BookService(db)

    # 상세 정보를 가져오면서 조회 수도 증가시킨다.
    book = service.get_book(book_id, increase_view=True)

    # 추천 분석에 사용할 최근 조회 기록을 저장한다.
    service.record_view(
        book_id,
        member.member_id if member else None,
        request.cookies.get("cart_session"),  # 비회원은 세션 키로 구분
    )

    # 로그인 회원이라면 이 도서를 위시리스트에 담았는지도 응답에 포함한다.
    return service.to_detail(
        book,
        member.member_id if member else None,
    )


@router.get(
    "/{book_id}/reviews",
    response_model=PageResponse[ReviewResponse],
    summary="도서 리뷰 목록",
)
def book_reviews(
    book_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=50),
    sort: str = Query(
        "recent",
        description="recent|rating_desc|rating_asc|like",
    ),
    sentiment: Optional[str] = Query(
        None,
        description="POSITIVE|NEUTRAL|NEGATIVE",
    ),
    rating: Optional[int] = Query(None, ge=1, le=5),  # 별점으로 필터링
    db: Session = Depends(get_db),
    member=Depends(get_current_member_optional),
):
    """도서 리뷰를 조회한다. 별점이나 감성 라벨로 필터링할 수 있다."""

    items, total = ReviewService(db).list_by_book(
        book_id,
        page,
        size,
        sort,
        sentiment,
        rating,
        member.member_id if member else None,
    )

    return PageResponse[ReviewResponse](
        items=items,
        meta=PageMeta.build(page, size, total),
    )


@router.get(
    "/{book_id}/review-stats",
    response_model=ReviewStatsResponse,
    summary="도서 리뷰 통계",
)
def book_review_stats(
    book_id: int,
    db: Session = Depends(get_db),
):
    """도서의 별점 분포와 감성 분석 요약을 반환한다."""
    return ReviewService(db).book_stats(book_id)


@router.get(
    "/{book_id}/similar",
    response_model=List[BookListItem],
    summary="유사 도서 추천",
)
def similar_books(
    book_id: int,
    limit: int = Query(8, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """AI가 계산한 도서 간 유사도를 바탕으로 비슷한 책을 추천한다."""

    # 이 API에서만 쓰는 추천 기능을 요청 처리 시 불러온다.
    from team_backend.app.ai.recommender import get_recommender

    recommender = get_recommender(db)

    # 각 항목에는 도서 번호와 유사도 관련 값이 들어 있다고 가정한다.
    pairs = recommender.similar_books(book_id, limit)

    # 추천된 도서 번호만 뽑아 도서 목록 응답으로 변환한다.
    return BookService(db).list_by_ids([
        bid for bid, _ in pairs
    ])


@router.get(
    "/{book_id}/bought-together",
    response_model=List[BookListItem],
    summary="함께 구매한 도서",
)
def bought_together(
    book_id: int,
    limit: int = Query(6, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """연관 규칙 분석 결과를 바탕으로 함께 구매한 책을 추천한다."""

    from team_backend.app.ai.recommender import AssociationRuleMiner

    # 기준 도서와 함께 구매되는 경향이 있는 도서 목록을 구한다.
    pairs = AssociationRuleMiner(db).frequently_bought_together(
        book_id,
        limit,
    )

    # 분석 결과에서 도서 번호만 뽑아 도서 응답 스키마로 바꾼다.
    return BookService(db).list_by_ids([
        bid for bid, _ in pairs
    ])