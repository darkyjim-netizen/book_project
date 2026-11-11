from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.api_errors import api_error
from app.models.cart_model import CartItem
from app.models.order_model import Order, OrderStatus, OrderStatusHistory
from app.models.product_model import Product
from app.routers.order_schemas import OrderInput


# PG사 주문 ID로 쓸 수 있는 형식(영문·숫자·하이픈, 6~64자)의 주문번호를 만듭니다.
def new_order_number() -> str:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"ORD-{today}-{uuid4().hex[:10].upper()}"


# 주문 ID로 주문을 조회합니다. 회원 ID를 주면 본인의 주문만 찾습니다.
def get_order_by_id(db: Session, order_id: int, member_id: int | None = None) -> Order | None:
    query = select(Order).where(Order.id == order_id)
    if member_id is not None:
        query = query.where(Order.member_id == member_id)
    return db.scalar(query)


# PG사가 돌려준 주문번호로 주문을 조회합니다.
def get_order_by_number(db: Session, order_number: str) -> Order | None:
    return db.scalar(select(Order).where(Order.order_number == order_number))


# 상품과 재고를 검증한 뒤 재고 차감, 장바구니 정리, 주문 저장을 처리합니다.
def place_order(db: Session, member_id: int, data: OrderInput) -> Order:
    # 상품별 주문 수량을 묶어 같은 상품이 중복 입력되었는지 확인합니다.
    quantities = {item.product_id: item.quantity for item in data.items}
    if len(quantities) != len(data.items):
        raise api_error(400, "INVALID_INPUT_VALUE", "같은 상품을 주문 항목에 두 번 입력할 수 없습니다.")

    # 주문할 상품을 ID 순서로 잠가 동시에 주문할 때 재고 변경이 겹치지 않게 합니다.
    products = list(db.scalars(select(Product).where(
        Product.id.in_(quantities), Product.active.is_(True)).order_by(Product.id).with_for_update()))
    if len(products) != len(quantities):
        raise api_error(404, "PRODUCT_NOT_FOUND", "주문할 수 없는 도서가 있습니다.")
    # 하나라도 주문 수량보다 재고가 부족하면 주문을 중단합니다.
    if any(product.stock < quantities[product.id] for product in products):
        raise api_error(400, "OUT_OF_STOCK", "주문 수량만큼 재고가 남아 있지 않습니다.")

    # 재고를 차감하면서 주문 당시의 제목과 가격을 주문 항목에 보관합니다.
    lines = []
    for product in products:
        quantity = quantities[product.id]
        product.stock -= quantity
        lines.append({"product_id": product.id, "title": product.title, "category_id": product.category_id,
                      "quantity": quantity, "unit_price": product.price})

    # 주문한 상품의 장바구니 항목을 잠그고 구매한 수량만큼 정리합니다.
    cart_items = db.scalars(select(CartItem).where(
        CartItem.member_id == member_id, CartItem.product_id.in_(quantities)).with_for_update())
    for item in cart_items:
        remaining = item.quantity - quantities[item.product_id]
        if remaining > 0:
            item.quantity = remaining
        else:
            db.delete(item)

    # 테스트 결제는 주문과 동시에 결제 완료로, 토스 결제는 승인 전까지 결제 대기로 저장합니다.
    method = data.payment_info.method
    is_test = method == "test"
    status = OrderStatus.PAID if is_test else OrderStatus.PENDING

    # 각 상품의 수량과 단가를 곱한 합계로 주문 총액을 계산합니다.
    order = Order(
        order_number=new_order_number(),
        member_id=member_id, receiver_name=data.receiver_name, address=data.address,
        items=lines, total=sum(line["quantity"] * line["unit_price"] for line in lines),
        region=data.region, age_group=data.age_group,
        status=status.value, payment_method=method,
        payment_status="test_paid" if is_test else status.value,
        paid_at=datetime.now(timezone.utc) if is_test else None,
    )
    db.add(order)
    # 이력에 넣을 주문 ID를 먼저 받아 옵니다.
    db.flush()
    db.add(OrderStatusHistory(order_id=order.id, from_status=None, to_status=status.value,
                              changed_by=member_id, reason="주문 생성"))
    # 주문 저장, 재고 차감, 장바구니 변경을 하나의 트랜잭션으로 반영합니다.
    db.commit()
    db.refresh(order)
    return order
