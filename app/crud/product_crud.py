from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.api_errors import api_error
from app.models.category_model import Category
from app.models.product_model import Product


def find_product(db: Session, product_id: int, *, lock: bool = False) -> Product:
    query = select(Product).where(Product.id == product_id, Product.active.is_(True))
    product = db.scalar(query.with_for_update() if lock else query)
    if product is None:
        raise api_error(404, "PRODUCT_NOT_FOUND", "도서를 찾을 수 없습니다.")
    return product


def check_category(db: Session, category_id: int) -> None:
    if db.get(Category, category_id) is None:
        raise api_error(400, "INVALID_INPUT_VALUE", "등록된 카테고리를 선택해 주세요.")


def list_products(db: Session, page: int, size: int, sort_by: str, direction: str,
                  keyword: str | None, category_id: int | None) -> tuple[list[Product], int]:
    query = select(Product).where(Product.active.is_(True))
    if keyword:
        query = query.where(or_(Product.title.icontains(keyword, autoescape=True),
                                Product.author.icontains(keyword, autoescape=True)))
    if category_id is not None:
        query = query.where(Product.category_id == category_id)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    column = {"created_at": Product.created_at, "price": Product.price}[sort_by]
    sort = column.asc() if direction == "asc" else column.desc()
    items = list(db.scalars(query.order_by(sort, Product.id).offset((page - 1) * size).limit(size)))
    return items, total
