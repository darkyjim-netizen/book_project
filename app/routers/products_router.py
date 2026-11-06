from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.auth_dependencies import admin_member
from app.crud.product_crud import check_category, find_product, list_products
from app.database import get_db
from app.models.product_model import Product
from app.routers.page_schema import PageResponse
from app.routers.product_schemas import ProductInput, ProductResponse


router = APIRouter(prefix="/api/products", tags=["도서"])
admin_only = [Depends(admin_member)]


@router.get("", response_model=PageResponse[ProductResponse])
def products(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    sort_by: Literal["created_at", "price"] = "created_at",
    direction: Literal["asc", "desc"] = "desc",
    keyword: str | None = Query(None, max_length=200),
    category_id: int | None = Query(None, gt=0),
):
    items, total = list_products(db, page, size, sort_by, direction, keyword, category_id)
    return {"items": items, "total": total, "page": page, "size": size}


@router.get("/{product_id}", response_model=ProductResponse)
def product(product_id: int, db: Session = Depends(get_db)):
    return find_product(db, product_id)


@router.post("", status_code=201, response_model=ProductResponse, dependencies=admin_only)
def create_product(data: ProductInput, db: Session = Depends(get_db)):
    check_category(db, data.category_id)
    product = Product(**data.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.put("/{product_id}", response_model=ProductResponse, dependencies=admin_only)
def replace_product(product_id: int, data: ProductInput, db: Session = Depends(get_db)):
    product = find_product(db, product_id, lock=True)
    check_category(db, data.category_id)
    for field, value in data.model_dump().items():
        setattr(product, field, value)
    db.commit()
    return product


@router.delete("/{product_id}", dependencies=admin_only)
def remove_product(product_id: int, db: Session = Depends(get_db)):
    product = find_product(db, product_id, lock=True)
    product.active = False
    db.commit()
    return {"deleted": True}
