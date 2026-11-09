from datetime import datetime
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.routers.cart_router import CartInput


# 테스트 결제 방식만 허용하고 정의되지 않은 결제 필드는 거부합니다.
class PaymentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: Literal["test"]


# 배송지, 주문 항목, 결제 방식과 선택 통계 정보를 검증합니다.
class OrderInput(BaseModel):
    receiver_name: str = Field(validation_alias=AliasChoices("receiver_name", "ReceiverName"), min_length=1, max_length=100)
    address: str = Field(validation_alias=AliasChoices("address", "Address"), min_length=1, max_length=500)
    payment_info: PaymentInput = Field(validation_alias=AliasChoices("payment_info", "PaymentInfo"))
    items: list[CartInput] = Field(validation_alias=AliasChoices("items", "Items"), min_length=1, max_length=100)
    region: str | None = Field(default=None, max_length=40)
    age_group: Literal["10대", "20대", "30대", "40대", "50대", "60대 이상"] | None = None


# 주문 시점의 도서 제목, 단가, 분류를 주문 항목에 포함합니다.
class OrderLineResponse(CartInput):
    title: str
    unit_price: int
    category_id: int


# 저장된 주문 객체를 배송지, 항목, 총액 등의 응답 데이터로 변환합니다.
class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    receiver_name: str
    address: str
    items: list[OrderLineResponse]
    total: int
    payment_status: str
    created_at: datetime
