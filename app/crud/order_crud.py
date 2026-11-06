from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.api_errors import api_error
from app.models.cart_model import CartItem
from app.models.order_model import Order
from app.models.product_model import Product
from app.routers.order_schemas import OrderInput


def place_order(db: Session, member_id: int, data: OrderInput) -> Order:
    quantities = {item.product_id: item.quantity for item in data.items}
    if len(quantities) != len(data.items):
        raise api_error(400, "INVALID_INPUT_VALUE", "같은 상품을 주문 항목에 두 번 입력할 수 없습니다.")

    products = list(db.scalars(select(Product).where(
        Product.id.in_(quantities), Product.active.is_(True)).order_by(Product.id).with_for_update()))
    if len(products) != len(quantities):
        raise api_error(404, "PRODUCT_NOT_FOUND", "주문할 수 없는 도서가 있습니다.")
    if any(product.stock < quantities[product.id] for product in products):
        raise api_error(400, "OUT_OF_STOCK", "주문 수량만큼 재고가 남아 있지 않습니다.")

    lines = []
    for product in products:
        quantity = quantities[product.id]
        product.stock -= quantity
        lines.append({"product_id": product.id, "title": product.title, "category_id": product.category_id,
                      "quantity": quantity, "unit_price": product.price})

    cart_items = db.scalars(select(CartItem).where(
        CartItem.member_id == member_id, CartItem.product_id.in_(quantities)).with_for_update())
    for item in cart_items:
        remaining = item.quantity - quantities[item.product_id]
        if remaining > 0:
            item.quantity = remaining
        else:
            db.delete(item)

    order = Order(
        member_id=member_id, receiver_name=data.receiver_name, address=data.address,
        items=lines, total=sum(line["quantity"] * line["unit_price"] for line in lines),
        region=data.region, age_group=data.age_group,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order
