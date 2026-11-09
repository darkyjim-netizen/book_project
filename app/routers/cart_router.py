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


# 장바구니 상품 수량을 1개부터 99개까지로 제한합니다.
class CartQuantity(BaseModel):
    quantity: int = Field(validation_alias=AliasChoices("quantity", "Quantity"), ge=1, le=99)


# 장바구니에 담을 상품 ID와 수량을 검증합니다.
class CartInput(CartQuantity):
    product_id: int = Field(validation_alias=AliasChoices("product_id", "ProductId"), gt=0)


# 장바구니 객체를 상품 ID, 수량, 항목 ID로 응답합니다.
class CartItemResponse(CartInput):
    model_config = ConfigDict(from_attributes=True)

    id: int


# 현재 회원 소유의 장바구니 항목만 조회하고 수정할 행을 잠급니다.
def owned_item(db: Session, member_id: int, cart_item_id: int) -> CartItem:
    item = db.scalar(select(CartItem).where(
        CartItem.id == cart_item_id, CartItem.member_id == member_id).with_for_update())
    if item is None:
        raise api_error(404, "CART_ITEM_NOT_FOUND", "장바구니 항목을 찾을 수 없습니다.")
    return item


# 요청 수량이 현재 재고를 초과하면 오류를 발생시킵니다.
def check_stock(stock: int, quantity: int) -> None:
    if stock < quantity:
        raise api_error(400, "OUT_OF_STOCK", "재고가 부족합니다.")


# 로그인한 회원의 장바구니 목록을 항목 ID 순으로 반환합니다.
@router.get("", response_model=list[CartItemResponse])
def cart(member: Member = Depends(current_member), db: Session = Depends(get_db)):
    return list(db.scalars(select(CartItem).where(CartItem.member_id == member.id).order_by(CartItem.id)))


# 재고를 확인하고 새 상품을 담거나 기존 항목에 수량을 더합니다.
@router.post("", status_code=201, response_model=CartItemResponse,
             responses={200: {"model": CartItemResponse}})
def add_item(data: CartInput, response: Response, member: Member = Depends(current_member), db: Session = Depends(get_db)):
    # 상품 행을 잠가 재고 확인 중 다른 요청의 상품 변경과 충돌하지 않게 합니다.
    product = find_product(db, data.product_id, lock=True)
    item = db.scalar(select(CartItem).where(
        CartItem.member_id == member.id, CartItem.product_id == product.id).with_for_update())
    # 기존에 담긴 수량이 있으면 이번 요청 수량과 합칩니다.
    quantity = data.quantity + (item.quantity if item else 0)
    if quantity > 99:
        raise api_error(400, "INVALID_INPUT_VALUE", "상품당 최대 99개까지 담을 수 있습니다.")
    check_stock(product.stock, quantity)
    if item is None:
        item = CartItem(member_id=member.id, product_id=product.id, quantity=quantity)
        db.add(item)
    else:
        # 새 항목 생성이 아닌 기존 항목 수정이므로 성공 코드를 200으로 바꿉니다.
        response.status_code = 200
        item.quantity = quantity
    db.commit()
    db.refresh(item)
    return item


# 회원 소유 항목의 재고를 확인한 뒤 장바구니 수량을 변경합니다.
@router.patch("/{cart_item_id}", response_model=CartItemResponse)
def change_item(cart_item_id: int, data: CartQuantity, member: Member = Depends(current_member),
                db: Session = Depends(get_db)):
    # 현재 회원의 장바구니에서 상품 ID를 확인한 뒤 상품부터 잠급니다.
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


# 로그인한 회원 소유의 장바구니 항목을 삭제합니다.
@router.delete("/{cart_item_id}")
def delete_item(cart_item_id: int, member: Member = Depends(current_member), db: Session = Depends(get_db)):
    db.delete(owned_item(db, member.id, cart_item_id))
    db.commit()
    return {"deleted": True}
