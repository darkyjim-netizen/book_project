from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.api_errors import api_error
from app.models.category_model import Category
from app.models.product_model import Product


# 판매 중인 도서를 조회하고 필요하면 수정 충돌을 막기 위해 행을 잠급니다.
def find_product(db: Session, product_id: int, *, lock: bool = False) -> Product:
    query = select(Product).where(Product.id == product_id, Product.active.is_(True))
    product = db.scalar(query.with_for_update() if lock else query)
    if product is None:
        raise api_error(404, "PRODUCT_NOT_FOUND", "도서를 찾을 수 없습니다.")
    return product


# 입력한 카테고리가 데이터베이스에 등록되어 있는지 확인합니다.
def check_category(db: Session, category_id: int) -> None:
    if db.get(Category, category_id) is None:
        raise api_error(400, "INVALID_INPUT_VALUE", "등록된 카테고리를 선택해 주세요.")


# 검색·분류·정렬 조건으로 도서 목록을 조회하고 전체 개수를 반환합니다.
def list_products(db: Session, page: int, size: int, sort_by: str, direction: str,
                  keyword: str | None, category_id: int | None) -> tuple[list[Product], int]:
    query = select(Product).where(Product.active.is_(True))
    # 검색어를 SQL 와일드카드가 아닌 일반 문자로 취급하여 제목과 저자를 검색합니다.
    if keyword:
        query = query.where(or_(Product.title.icontains(keyword, autoescape=True),
                                Product.author.icontains(keyword, autoescape=True)))
    if category_id is not None:
        query = query.where(Product.category_id == category_id)
    # 페이지 범위를 적용하기 전에 검색 조건에 맞는 전체 도서 수를 계산합니다.
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    column = {"created_at": Product.created_at, "price": Product.price}[sort_by]
    sort = column.asc() if direction == "asc" else column.desc()
    # 정렬 후 앞 페이지의 항목을 건너뛰고 요청한 개수만 조회합니다.
    items = list(db.scalars(query.order_by(sort, Product.id).offset((page - 1) * size).limit(size)))
    return items, total
