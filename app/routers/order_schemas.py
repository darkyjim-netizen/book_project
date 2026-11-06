from datetime import datetime
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.routers.cart_router import CartInput


class PaymentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: Literal["test"]


class OrderInput(BaseModel):
    receiver_name: str = Field(validation_alias=AliasChoices("receiver_name", "ReceiverName"), min_length=1, max_length=100)
    address: str = Field(validation_alias=AliasChoices("address", "Address"), min_length=1, max_length=500)
    payment_info: PaymentInput = Field(validation_alias=AliasChoices("payment_info", "PaymentInfo"))
    items: list[CartInput] = Field(validation_alias=AliasChoices("items", "Items"), min_length=1, max_length=100)
    region: str | None = Field(default=None, max_length=40)
    age_group: Literal["10대", "20대", "30대", "40대", "50대", "60대 이상"] | None = None


class OrderLineResponse(CartInput):
    title: str
    unit_price: int
    category_id: int


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    receiver_name: str
    address: str
    items: list[OrderLineResponse]
    total: int
    payment_status: str
    created_at: datetime
