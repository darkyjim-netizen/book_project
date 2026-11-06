from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.auth_dependencies import current_member
from app.core.api_errors import api_error
from app.crud.order_crud import place_order
from app.database import get_db
from app.models.order_model import Order
from app.models.user_model import Member
from app.routers.order_schemas import OrderInput, OrderResponse
from app.routers.page_schema import PageResponse


router = APIRouter(prefix="/api/orders", tags=["주문"])


@router.get("", response_model=PageResponse[OrderResponse])
def orders(member: Member = Depends(current_member), db: Session = Depends(get_db),
           page: int = Query(1, ge=1), size: int = Query(10, ge=1, le=100)):
    query = select(Order).where(Order.member_id == member.id)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = list(db.scalars(query.order_by(Order.id.desc()).offset((page - 1) * size).limit(size)))
    return {"items": items, "total": total, "page": page, "size": size}


@router.post("", response_model=OrderResponse, status_code=201)
def create_order(data: OrderInput, member: Member = Depends(current_member), db: Session = Depends(get_db)):
    return place_order(db, member.id, data)


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(order_id: int, member: Member = Depends(current_member), db: Session = Depends(get_db)):
    order = db.scalar(select(Order).where(Order.id == order_id, Order.member_id == member.id))
    if order is None:
        raise api_error(404, "ORDER_NOT_FOUND", "주문을 찾을 수 없습니다.")
    return order
