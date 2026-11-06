from fastapi import APIRouter, Depends, Response
from pydantic import AliasChoices, BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.auth_dependencies import current_member
from app.core.api_errors import api_error
from app.crud.product_crud import find_product
from app.database import get_db
from app.models.cart_model import CartItem
from app.models.user_model import Member


router = APIRouter(prefix="/api/cart", tags=["장바구니"])


class CartQuantity(BaseModel):
    quantity: int = Field(validation_alias=AliasChoices("quantity", "Quantity"), ge=1, le=99)


class CartInput(CartQuantity):
    product_id: int = Field(validation_alias=AliasChoices("product_id", "ProductId"), gt=0)


class CartItemResponse(CartInput):
    model_config = ConfigDict(from_attributes=True)

    id: int


def owned_item(db: Session, member_id: int, cart_item_id: int) -> CartItem:
    item = db.scalar(select(CartItem).where(
        CartItem.id == cart_item_id, CartItem.member_id == member_id).with_for_update())
    if item is None:
        raise api_error(404, "CART_ITEM_NOT_FOUND", "장바구니 항목을 찾을 수 없습니다.")
    return item


def check_stock(stock: int, quantity: int) -> None:
    if stock < quantity:
        raise api_error(400, "OUT_OF_STOCK", "재고가 부족합니다.")


@router.get("", response_model=list[CartItemResponse])
def cart(member: Member = Depends(current_member), db: Session = Depends(get_db)):
    return list(db.scalars(select(CartItem).where(CartItem.member_id == member.id).order_by(CartItem.id)))


@router.post("", status_code=201, response_model=CartItemResponse,
             responses={200: {"model": CartItemResponse}})
def add_item(data: CartInput, response: Response, member: Member = Depends(current_member), db: Session = Depends(get_db)):
    product = find_product(db, data.product_id, lock=True)
    item = db.scalar(select(CartItem).where(
        CartItem.member_id == member.id, CartItem.product_id == product.id).with_for_update())
    quantity = data.quantity + (item.quantity if item else 0)
    if quantity > 99:
        raise api_error(400, "INVALID_INPUT_VALUE", "상품당 최대 99개까지 담을 수 있습니다.")
    check_stock(product.stock, quantity)
    if item is None:
        item = CartItem(member_id=member.id, product_id=product.id, quantity=quantity)
        db.add(item)
    else:
        response.status_code = 200
        item.quantity = quantity
    db.commit()
    db.refresh(item)
    return item


@router.patch("/{cart_item_id}", response_model=CartItemResponse)
def change_item(cart_item_id: int, data: CartQuantity, member: Member = Depends(current_member),
                db: Session = Depends(get_db)):
    product_id = db.scalar(select(CartItem.product_id).where(
        CartItem.id == cart_item_id, CartItem.member_id == member.id))
    if product_id is None:
        raise api_error(404, "CART_ITEM_NOT_FOUND", "장바구니 항목을 찾을 수 없습니다.")
    product = find_product(db, product_id, lock=True)
    item = owned_item(db, member.id, cart_item_id)
    check_stock(product.stock, data.quantity)
    item.quantity = data.quantity
    db.commit()
    return item


@router.delete("/{cart_item_id}")
def delete_item(cart_item_id: int, member: Member = Depends(current_member), db: Session = Depends(get_db)):
    db.delete(owned_item(db, member.id, cart_item_id))
    db.commit()
    return {"deleted": True}
