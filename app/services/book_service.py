"""도서 조회, 검색, 등록, 수정과 재고 관리를 담당하는 서비스."""
import logging
from typing import List, Optional, Tuple

from sqlalchemy import Select, and_, func, or_, select, text
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import BusinessError, NotFoundError
from app.models.book import (
    Author,
    Book,
    BookAuthor,
    BookImage,
    Category,
    Publisher,
    RecentView,
    SearchLog,
    StockHistory,
)
from app.models.cart import Wishlist
from app.models.enums import BookStatus
from app.schemas.book import (
    BookCreateRequest,
    BookDetailResponse,
    BookListItem,
    BookSearchParams,
    BookUpdateRequest,
)

logger = logging.getLogger(__name__)


# 검색 결과의 정렬 이름과 SQLAlchemy 정렬 조건을 연결한다.
SORT_MAP = {
    "recent": (Book.published_date.desc().nullslast(), Book.book_id.desc()),
    "sales": (Book.sales_count.desc(), Book.book_id.desc()),
    "price_asc": (Book.sale_price.asc(),),
    "price_desc": (Book.sale_price.desc(),),
    "rating": (Book.rating_avg.desc(), Book.review_count.desc()),
    "review": (Book.review_count.desc(),),
    "title": (Book.title.asc(),),
}


class BookService:
    """도서 관련 DB 조회와 업무 규칙을 처리한다."""

    def __init__(self, db: Session):
        self.db = db  # 이 서비스에서 사용할 DB 세션

    # ------------------------------------------------------------------ 변환
    @staticmethod
    def to_list_item(book: Book) -> BookListItem:
        """도서 ORM 객체를 목록용 응답 스키마로 바꾼다."""

        return BookListItem(
            book_id=book.book_id,
            isbn13=book.isbn13,
            title=book.title,
            subtitle=book.subtitle,
            authors=book.author_names,  # 도서 모델의 저자 이름 목록 속성
            publisher=book.publisher.name if book.publisher else None,
            category_name=book.category.name if book.category else None,
            list_price=float(book.list_price),
            sale_price=float(book.sale_price),
            discount_rate=float(book.discount_rate),
            cover_image=book.cover_image,
            status=book.status.value,  # Enum 객체 대신 문자열 값 반환
            stock_qty=book.stock_qty,
            rating_avg=float(book.rating_avg),
            review_count=book.review_count,
            sales_count=book.sales_count,
            is_domestic=book.is_domestic,
            published_date=book.published_date,
        )

    def to_detail(
        self,
        book: Book,
        member_id: Optional[int] = None,
    ) -> BookDetailResponse:
        """도서 ORM 객체를 상세 페이지용 응답 스키마로 바꾼다."""

        # 목록용 정보를 먼저 만들고 딕셔너리로 변환한다.
        base = self.to_list_item(book).model_dump()

        # 로그인 회원이 위시리스트에 이 책을 담았는지 확인한다.
        is_wished = False
        if member_id:
            is_wished = (
                self.db.scalar(
                    select(func.count())
                    .select_from(Wishlist)
                    .where(
                        Wishlist.member_id == member_id,
                        Wishlist.book_id == book.book_id,
                    )
                )
                or 0
            ) > 0

        # 목록 정보에 상세 설명과 이미지 등을 추가한다.
        return BookDetailResponse(
            **base,
            translator=book.translator,
            page_count=book.page_count,
            binding=book.binding,
            size_mm=book.size_mm,
            weight_g=book.weight_g,
            language_code=book.language_code,
            summary=book.summary,
            description=book.description,
            table_of_contents=book.table_of_contents,
            publisher_review=book.publisher_review,
            point_rate=float(book.point_rate),
            view_count=book.view_count,
            sentiment_score=(
                float(book.sentiment_score)
                if book.sentiment_score
                else None
            ),
            # 이미지 표시 순서에 맞게 정렬한 뒤 주소만 추린다.
            images=[
                image.image_url
                for image in sorted(book.images, key=lambda image: image.sort_order)
            ],
            is_wished=is_wished,
        )

    # ------------------------------------------------------------------ 조회
    def _base_query(self) -> Select:
        """저자 정보를 함께 불러오도록 기본 도서 조회문을 만든다."""

        return select(Book).options(
            # 도서-저자 연결 정보를 읽고, 연결된 저자 정보도 함께 읽는다.
            selectinload(Book.book_authors).selectinload(BookAuthor.author)
        )

    def get_book(
        self,
        book_id: int,
        increase_view: bool = False,
    ) -> Book:
        """도서 번호로 도서를 조회한다."""

        book = self.db.scalar(
            self._base_query()
            # 상세 화면에서 사용할 이미지도 함께 불러온다.
            .options(selectinload(Book.images))
            .where(Book.book_id == book_id)
        )

        # 도서가 없거나 논리 삭제 상태라면 조회 불가로 처리한다.
        if book is None or book.status == BookStatus.DELETED:
            raise NotFoundError("도서를 찾을 수 없습니다.")

        if increase_view:
            # 상세 조회 시 조회 수를 1 증가시키고 바로 저장한다.
            book.view_count = (book.view_count or 0) + 1
            self.db.commit()

        return book

    def get_by_isbn(self, isbn13: str) -> Book:
        """ISBN-13으로 도서를 조회한다."""

        book = self.db.scalar(
            self._base_query().where(Book.isbn13 == isbn13)
        )
        if book is None:
            raise NotFoundError("도서를 찾을 수 없습니다.")
        return book

    def _descendant_category_ids(self, category_id: int) -> List[int]:
        """지정한 카테고리와 모든 하위 카테고리 번호를 찾는다."""

        # 재귀 CTE는 상위 카테고리에서 시작해 하위 카테고리를 차례로 탐색한다.
        sql = text(
            """
            WITH RECURSIVE tree AS (
                SELECT category_id
                  FROM shop.categories
                 WHERE category_id = :cid

                UNION ALL

                SELECT c.category_id
                  FROM shop.categories c
                  JOIN tree t ON c.parent_id = t.category_id
            )
            SELECT category_id FROM tree
            """
        )

        # :cid 자리에 category_id 값을 전달하고 결과의 첫 번째 열을 목록으로 만든다.
        return [
            row[0]
            for row in self.db.execute(sql, {"cid": category_id})
        ]

    def search(
        self,
        params: BookSearchParams,
        member_id: Optional[int] = None,
    ) -> Tuple[List[BookListItem], int]:
        """검색 조건에 맞는 도서 목록과 전체 검색 건수를 반환한다."""

        # 삭제된 도서는 모든 일반 검색 결과에서 제외한다.
        conditions = [Book.status != BookStatus.DELETED]

        if params.keyword:
            # 앞뒤 공백을 제거한 검색어를 부분 검색에 쓸 형식으로 만든다.
            kw = f"%{params.keyword.strip()}%"

            # 저자 이름으로 검색된 도서 번호를 찾는 하위 쿼리
            author_subq = (
                select(BookAuthor.book_id)
                .join(Author, Author.author_id == BookAuthor.author_id)
                .where(Author.name.ilike(kw))
            )

            # 제목, 부제, 소개, ISBN, 저자명 중 하나라도 일치하면 포함한다.
            conditions.append(
                or_(
                    Book.title.ilike(kw),
                    Book.subtitle.ilike(kw),
                    Book.summary.ilike(kw),
                    Book.isbn13 == params.keyword.strip(),
                    Book.book_id.in_(author_subq),
                )
            )

        if params.category_id:
            # 선택한 카테고리뿐 아니라 하위 카테고리의 도서도 포함한다.
            conditions.append(
                Book.category_id.in_(
                    self._descendant_category_ids(params.category_id)
                )
            )

        if params.publisher_id:
            conditions.append(Book.publisher_id == params.publisher_id)

        if params.author_id:
            # 선택한 저자가 참여한 도서 번호를 하위 쿼리로 찾는다.
            conditions.append(
                Book.book_id.in_(
                    select(BookAuthor.book_id).where(
                        BookAuthor.author_id == params.author_id
                    )
                )
            )

        if params.min_price is not None:
            conditions.append(Book.sale_price >= params.min_price)

        if params.max_price is not None:
            conditions.append(Book.sale_price <= params.max_price)

        if params.is_domestic is not None:
            conditions.append(Book.is_domestic == params.is_domestic)

        if params.in_stock_only:
            # 재고가 있고 판매 상태인 도서만 조회한다.
            conditions.append(
                and_(
                    Book.stock_qty > 0,
                    Book.status == BookStatus.SALE,
                )
            )

        # 모든 필터 조건을 AND로 묶는다.
        where = and_(*conditions)

        # 페이지 제한을 적용하기 전에 전체 검색 결과 수를 센다.
        total = (
            self.db.scalar(
                select(func.count()).select_from(Book).where(where)
            )
            or 0
        )

        stmt = self._base_query().where(where)

        # 요청한 정렬 방식으로 결과 순서를 지정한다.
        # 알 수 없는 정렬값이면 최근 출간순을 기본으로 사용한다.
        for order in SORT_MAP.get(params.sort, SORT_MAP["recent"]):
            stmt = stmt.order_by(order)

        # 페이지 번호와 페이지당 건수에 따라 가져올 범위를 정한다.
        stmt = stmt.offset(
            (params.page - 1) * params.size
        ).limit(params.size)

        books = list(self.db.scalars(stmt).unique())

        if params.keyword:
            # 검색어와 검색 결과 수를 기록한다.
            # member_id가 None이면 비회원 검색 기록이다.
            self.db.add(
                SearchLog(
                    member_id=member_id,
                    keyword=params.keyword.strip(),
                    result_count=total,
                )
            )
            self.db.commit()

        # ORM 객체를 목록 응답 스키마로 바꿔 반환한다.
        return [self.to_list_item(book) for book in books], total

    def list_bestsellers(
        self,
        limit: int = 10,
        category_id: Optional[int] = None,
    ) -> List[BookListItem]:
        """판매 수량이 많은 도서를 조회한다."""

        stmt = self._base_query().where(Book.status == BookStatus.SALE)

        if category_id:
            # 카테고리를 지정하면 하위 카테고리 상품도 포함한다.
            stmt = stmt.where(
                Book.category_id.in_(
                    self._descendant_category_ids(category_id)
                )
            )

        stmt = stmt.order_by(Book.sales_count.desc()).limit(limit)
        return [
            self.to_list_item(book)
            for book in self.db.scalars(stmt).unique()
        ]

    def list_new_releases(self, limit: int = 10) -> List[BookListItem]:
        """판매 중인 도서 중 최근 출간된 도서를 조회한다."""

        stmt = (
            self._base_query()
            .where(Book.status == BookStatus.SALE)
            .order_by(Book.published_date.desc().nullslast())
            .limit(limit)
        )
        return [
            self.to_list_item(book)
            for book in self.db.scalars(stmt).unique()
        ]

    def list_by_ids(self, book_ids: List[int]) -> List[BookListItem]:
        """도서 번호 목록에 담긴 순서대로 도서를 반환한다."""

        if not book_ids:
            return []

        # IN 조건으로 도서들을 조회하고, 번호를 키로 삼아 딕셔너리에 담는다.
        books = {
            book.book_id: book
            for book in self.db.scalars(
                self._base_query().where(Book.book_id.in_(book_ids))
            ).unique()
        }

        # DB 조회 순서에 의존하지 않고 입력된 book_ids 순서를 기준으로 반환한다.
        return [
            self.to_list_item(books[book_id])
            for book_id in book_ids
            if book_id in books
        ]

    # ------------------------------------------------------------- 최근 본 상품
    def record_view(
        self,
        book_id: int,
        member_id: Optional[int],
        session_key: Optional[str],
        dwell: int = 0,
    ) -> None:
        """도서 조회 기록을 저장한다. 추천 분석 등에 활용할 수 있다."""

        self.db.add(
            RecentView(
                member_id=member_id,  # 로그인 회원이면 회원 번호
                session_key=session_key,  # 비회원이면 세션 식별값
                book_id=book_id,
                dwell_seconds=dwell,  # 도서 페이지에 머문 시간
            )
        )
        self.db.commit()

    def list_recent_views(
        self,
        member_id: int,
        limit: int = 10,
    ) -> List[BookListItem]:
        """회원이 최근 조회한 도서를 중복 없이 찾는다."""

        # 책별 마지막 조회 시각을 구하고 최근 조회한 책을 제한 수만큼 추린다.
        sub = (
            select(
                RecentView.book_id,
                func.max(RecentView.created_at).label("last_at"),
            )
            .where(RecentView.member_id == member_id)
            .group_by(RecentView.book_id)
            .order_by(func.max(RecentView.created_at).desc())
            .limit(limit)
            .subquery()
        )

        # 추린 도서 번호로 도서 정보를 조회한다.
        ids = [
            row[0]
            for row in self.db.execute(select(sub.c.book_id))
        ]

        # 참고: 바깥쪽 SELECT에 정렬 조건이 없어 DB가 반환하는 ID 순서는 보장되지 않는다.
        return self.list_by_ids(ids)

    # ------------------------------------------------------------------ 관리
    def create_book(self, payload: BookCreateRequest) -> Book:
        """새 도서를 등록하고 저자·초기 재고 기록을 만든다."""

        # ISBN이 이미 등록되어 있는지 확인한다.
        if self.db.scalar(
            select(Book).where(Book.isbn13 == payload.isbn13)
        ):
            raise BusinessError(
                "이미 등록된 ISBN 입니다.",
                code="ISBN_DUPLICATED",
            )

        # 연결할 카테고리와 출판사가 실제로 있는지 확인한다.
        if self.db.get(Category, payload.category_id) is None:
            raise NotFoundError("카테고리를 찾을 수 없습니다.")
        if self.db.get(Publisher, payload.publisher_id) is None:
            raise NotFoundError("출판사를 찾을 수 없습니다.")

        # 저자 번호와 상태는 별도로 처리하므로 일반 필드에서 제외한다.
        data = payload.model_dump(exclude={"author_ids", "status"})

        # 정가가 0이 아니면 정가와 판매가로 할인율을 계산한다.
        discount = 0.0
        if payload.list_price:
            discount = round(
                (1 - payload.sale_price / payload.list_price) * 100,
                2,
            )

        book = Book(
            **data,
            status=BookStatus(payload.status),
            discount_rate=discount,
        )
        self.db.add(book)

        # 도서 INSERT를 먼저 실행해 생성된 book_id를 얻는다.
        self.db.flush()

        # 도서와 저자의 연결 기록을 만든다.
        for idx, author_id in enumerate(payload.author_ids):
            self.db.add(
                BookAuthor(
                    book_id=book.book_id,
                    author_id=author_id,
                    role="AUTHOR",
                    sort_order=idx,
                )
            )

        # 초기 재고가 있으면 그 재고가 등록된 기록도 남긴다.
        if payload.stock_qty:
            self.db.add(
                StockHistory(
                    book_id=book.book_id,
                    change_qty=payload.stock_qty,
                    after_qty=payload.stock_qty,
                    reason="INITIAL",
                )
            )

        self.db.commit()
        self.db.refresh(book)
        logger.info("도서 등록: book_id=%s %s", book.book_id, book.title)
        return book

    def update_book(
        self,
        book_id: int,
        payload: BookUpdateRequest,
    ) -> Book:
        """도서 정보와 저자 목록을 수정한다."""

        book = self.db.get(Book, book_id)
        if book is None:
            raise NotFoundError("도서를 찾을 수 없습니다.")

        # 요청에 실제로 포함된 필드만 수정 대상으로 가져온다.
        # 저자와 상태는 아래에서 따로 처리한다.
        data = payload.model_dump(
            exclude_unset=True,
            exclude={"author_ids", "status"},
        )
        for key, value in data.items():
            setattr(book, key, value)

        # 상태값이 전달된 경우 Enum으로 변환해 저장한다.
        if payload.status:
            book.status = BookStatus(payload.status)

        # 정가가 있으면 수정된 가격을 기준으로 할인율을 다시 계산한다.
        if book.list_price:
            book.discount_rate = round(
                (1 - float(book.sale_price) / float(book.list_price)) * 100,
                2,
            )

        if payload.author_ids is not None:
            # 저자 목록을 전달한 경우 기존 연결을 지우고 새 목록으로 교체한다.
            self.db.query(BookAuthor).filter(
                BookAuthor.book_id == book_id
            ).delete()

            for idx, author_id in enumerate(payload.author_ids):
                self.db.add(
                    BookAuthor(
                        book_id=book_id,
                        author_id=author_id,
                        role="AUTHOR",
                        sort_order=idx,
                    )
                )

        self.db.commit()
        self.db.refresh(book)
        return book

    def delete_book(self, book_id: int) -> None:
        """도서를 실제 삭제하지 않고 삭제 상태로 바꾼다."""

        book = self.db.get(Book, book_id)
        if book is None:
            raise NotFoundError("도서를 찾을 수 없습니다.")

        book.status = BookStatus.DELETED
        self.db.commit()

    def adjust_stock(
        self,
        book_id: int,
        change_qty: int,
        reason: str,
        admin_id: Optional[int],
    ) -> Book:
        """재고를 변경하고 변경 이력을 저장한다."""

        book = self.db.get(Book, book_id)
        if book is None:
            raise NotFoundError("도서를 찾을 수 없습니다.")

        after = book.stock_qty + change_qty  # 변경 후 재고
        if after < 0:
            raise BusinessError("재고가 0보다 작아질 수 없습니다.")

        book.stock_qty = after

        # 품절 도서에 재고가 들어오면 판매 상태로 되돌린다.
        if after > 0 and book.status == BookStatus.SOLDOUT:
            book.status = BookStatus.SALE

        # 판매 중인 도서의 재고가 0이 되면 품절 상태로 바꾼다.
        elif after == 0 and book.status == BookStatus.SALE:
            book.status = BookStatus.SOLDOUT

        # 재고 수량 변경 전후와 사유를 기록한다.
        self.db.add(
            StockHistory(
                book_id=book_id,
                change_qty=change_qty,
                after_qty=after,
                reason=reason,
                created_by=admin_id,
            )
        )

        self.db.commit()
        self.db.refresh(book)
        return book

    def list_low_stock(self, limit: int = 50) -> List[BookListItem]:
        """판매 중이면서 재고가 안전 재고 이하인 도서를 조회한다."""

        stmt = (
            self._base_query()
            .where(
                Book.status == BookStatus.SALE,
                Book.stock_qty <= Book.safety_stock,
            )
            .order_by(Book.stock_qty.asc())
            .limit(limit)
        )
        return [
            self.to_list_item(book)
            for book in self.db.scalars(stmt).unique()
        ]

    # ------------------------------------------------------------ 카테고리 트리
    def category_tree(self) -> List[dict]:
        """활성 카테고리를 부모-자식 계층 구조로 반환한다."""

        # 활성 카테고리를 단계와 표시 순서대로 가져온다.
        rows = list(
            self.db.scalars(
                select(Category)
                .where(Category.is_active == True)  # noqa: E712
                .order_by(Category.depth, Category.sort_order)
            )
        )

        # 각 카테고리를 ID로 빠르게 찾을 수 있게 딕셔너리로 바꾼다.
        # 각 노드는 자식 노드를 담을 children 목록을 가진다.
        nodes = {
            category.category_id: {
                "category_id": category.category_id,
                "parent_id": category.parent_id,
                "name": category.name,
                "full_path": category.full_path,
                "depth": category.depth,
                "children": [],
            }
            for category in rows
        }

        roots = []
        for node in nodes.values():
            # 부모가 있으면 부모의 children 목록에 넣는다.
            parent = nodes.get(node["parent_id"]) if node["parent_id"] else None

            if parent:
                parent["children"].append(node)
            else:
                # 부모가 없는 카테고리는 최상위 노드다.
                roots.append(node)

        return roots

    def popular_keywords(self, limit: int = 10) -> List[dict]:
        """최근 7일 동안 많이 검색된 검색어를 조회한다."""

        sql = text(
            """
            SELECT keyword, COUNT(*) AS cnt
              FROM log.search_logs
             WHERE created_at >= now() - interval '7 days'
             GROUP BY keyword
             ORDER BY cnt DESC
             LIMIT :lim
            """
        )

        # 검색어별 횟수 집계를 내림차순으로 반환한다.
        return [
            {"keyword": row[0], "count": row[1]}
            for row in self.db.execute(sql, {"lim": limit})
        ]