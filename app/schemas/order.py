"""장바구니, 주문, 결제, 배송 API의 요청·응답 스키마."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# -----------------------------------------------------------------------------
# 장바구니
# -----------------------------------------------------------------------------
class CartItemAddRequest(BaseModel):
    """장바구니에 상품을 추가할 때 받는 데이터."""

    book_id: int  # 장바구니에 담을 도서 번호
    quantity: int = Field(
        1,
        ge=1,   # 수량은 최소 1개
        le=99,  # 한 번에 담는 수량은 최대 99개
    )


class CartItemUpdateRequest(BaseModel):
    """장바구니 상품의 수량이나 선택 상태를 바꿀 때 받는 데이터."""

    # 값이 전달된 항목만 수정하는 데 사용할 수 있다.
    quantity: Optional[int] = Field(None, ge=1, le=99)
    is_selected: Optional[bool] = None  # 주문할 상품으로 선택했는지 여부


class CartItemResponse(BaseModel):
    """장바구니에 담긴 상품 한 종류의 정보."""

    cart_item_id: int  # 장바구니 상품 항목 번호
    book_id: int  # 도서 번호
    title: str  # 도서 제목
    cover_image: Optional[str] = None  # 표지 이미지 주소
    authors: List[str] = []  # 저자 이름 목록
    unit_price: float  # 현재 적용되는 한 권 가격
    list_price: float  # 정가
    quantity: int  # 장바구니에 담긴 수량
    item_total: float  # 이 항목의 가격 합계
    is_selected: bool  # 주문 대상으로 선택됐는지 여부
    stock_qty: int  # 현재 재고
    status: str  # 도서 판매 상태
    is_available: bool  # 현재 구매할 수 있는지 여부


class CartResponse(BaseModel):
    """장바구니 전체 내용과 예상 결제 금액."""

    cart_id: Optional[int] = None  # 로그인 회원 등의 장바구니 번호
    items: List[CartItemResponse] = []  # 장바구니 상품 목록
    selected_count: int = 0  # 주문 대상으로 선택한 상품 수
    item_amount: float = 0  # 선택 상품 가격 합계
    discount_amount: float = 0  # 할인 금액
    ship_fee: float = 0  # 예상 배송비
    expected_point: float = 0  # 주문 완료 시 예상 적립 포인트
    total_amount: float = 0  # 예상 최종 결제 금액


# -----------------------------------------------------------------------------
# 주문
# -----------------------------------------------------------------------------
class OrderItemRequest(BaseModel):
    """주문할 도서 한 종류의 번호와 수량."""

    book_id: int
    quantity: int = Field(..., ge=1, le=99)  # 수량은 필수이며 1~99개


class OrderCreateRequest(BaseModel):
    """장바구니 상품을 주문하거나, 상품을 직접 지정해 주문할 때 받는 데이터."""

    # None이면 장바구니에서 선택한 상품을 주문 대상으로 사용한다.
    # 상품을 직접 주문할 때는 도서 번호와 수량 목록을 전달한다.
    items: Optional[List[OrderItemRequest]] = Field(
        None,
        description="미지정 시 장바구니의 선택 항목으로 주문 생성",
    )

    orderer_name: str = Field(..., max_length=60)  # 주문하는 사람
    orderer_phone: str = Field(..., max_length=20)  # 주문자 연락처
    orderer_email: EmailStr  # 이메일 형식 검사

    receiver: str = Field(..., max_length=60)  # 배송받는 사람
    receiver_phone: str = Field(..., max_length=20)  # 받는 사람 연락처
    zipcode: str = Field(..., max_length=10)  # 우편번호
    address1: str = Field(..., max_length=255)  # 기본 주소
    address2: Optional[str] = Field(None, max_length=255)  # 상세 주소
    request_memo: Optional[str] = Field(None, max_length=255)  # 배송 요청 사항

    is_gift_wrap: bool = False  # 선물 포장 여부
    member_coupon_id: Optional[int] = None  # 사용할 회원 쿠폰 번호
    point_used: int = Field(0, ge=0)  # 사용할 포인트. 음수는 허용하지 않는다.
    payment_method: str = Field("CARD")  # 결제 수단. 기본값은 카드

    @field_validator("payment_method")
    @classmethod
    def _method(cls, v: str):
        """결제 수단이 허용된 값인지 확인한다."""

        allowed = {
            "CARD",
            "VBANK",
            "TRANSFER",
            "PHONE",
            "KAKAOPAY",
            "NAVERPAY",
            "TOSSPAY",
            "POINT",
        }

        if v not in allowed:
            raise ValueError(f"지원하지 않는 결제 수단입니다: {v}")

        return v


class OrderItemResponse(BaseModel):
    """주문 안에 포함된 상품 한 종류의 응답 형식."""

    # SQLAlchemy 객체의 속성에서 응답 값을 읽도록 설정한다.
    model_config = ConfigDict(from_attributes=True)

    order_item_id: int  # 주문 상품 항목 번호
    book_id: int  # 도서 번호
    book_title: str  # 주문 당시 도서 제목
    cover_image: Optional[str] = None  # 표지 이미지 주소
    unit_price: float  # 주문 당시 한 권 가격
    quantity: int  # 주문 수량
    item_discount: float  # 상품 항목에 적용된 할인액
    item_total: float  # 해당 상품 항목의 합계
    status: str  # 상품 항목의 주문 처리 상태
    is_reviewed: bool  # 리뷰를 작성했는지 여부


class PaymentResponse(BaseModel):
    """주문에 연결된 결제 정보."""

    model_config = ConfigDict(from_attributes=True)

    payment_id: int  # 결제 번호
    method: str  # 결제 수단
    status: str  # 결제 상태
    amount: float  # 결제 금액
    pg_tid: Optional[str] = None  # 결제대행사가 발급한 거래 번호
    card_name: Optional[str] = None  # 카드사 이름
    card_no_masked: Optional[str] = None  # 일부를 가린 카드 번호
    vbank_bank: Optional[str] = None  # 가상계좌 은행
    vbank_no: Optional[str] = None  # 가상계좌 번호
    vbank_holder: Optional[str] = None  # 가상계좌 예금주
    vbank_due: Optional[datetime] = None  # 가상계좌 입금 기한
    receipt_url: Optional[str] = None  # 영수증 주소
    approved_at: Optional[datetime] = None  # 결제 승인 시각

    @field_validator("method", "status", mode="before")
    @classmethod
    def _enum(cls, v):
        """Enum 객체가 들어오면 실제 문자열 값으로 바꾼다."""
        # 예: PaymentStatus.PAID를 "PAID"로 바꾼다.
        return v.value if hasattr(v, "value") else v


class TrackingResponse(BaseModel):
    """배송 상태가 변경된 기록 한 건."""

    model_config = ConfigDict(from_attributes=True)

    status: str  # 해당 시점의 배송 상태
    location: Optional[str] = None  # 배송 처리 위치
    description: Optional[str] = None  # 상태 설명
    occurred_at: datetime  # 배송 상태가 발생한 시각

    @field_validator("status", mode="before")
    @classmethod
    def _enum(cls, v):
        """배송 상태 Enum을 문자열 값으로 바꾼다."""
        return v.value if hasattr(v, "value") else v


class ShipmentResponse(BaseModel):
    """주문의 배송 정보와 배송 이력."""

    model_config = ConfigDict(from_attributes=True)

    shipment_id: int  # 배송 번호
    carrier_code: str  # 택배사 코드
    carrier_name: str  # 택배사 이름
    invoice_no: Optional[str] = None  # 운송장 번호
    status: str  # 현재 배송 상태
    shipped_at: Optional[datetime] = None  # 발송 시각
    delivered_at: Optional[datetime] = None  # 배송 완료 시각
    tracking: List[TrackingResponse] = []  # 배송 상태 변경 이력 목록

    @field_validator("status", mode="before")
    @classmethod
    def _enum(cls, v):
        """배송 상태 Enum을 응답용 문자열로 바꾼다."""
        return v.value if hasattr(v, "value") else v


class OrderResponse(BaseModel):
    """주문 상세 정보를 반환할 때 사용하는 형식."""

    order_id: int  # 내부 주문 번호
    order_no: str  # 사용자에게 보여줄 주문 번호
    status: str  # 주문 상태 코드
    status_label: str  # 화면에 표시할 주문 상태 이름
    summary_title: str  # 주문 상품을 요약한 제목

    item_amount: float  # 상품 금액 합계
    discount_amount: float  # 전체 할인 금액
    coupon_amount: float  # 쿠폰 할인 금액
    point_used: float  # 사용한 포인트
    ship_fee: float  # 배송비
    total_amount: float  # 최종 결제 금액
    point_saved: float  # 적립된 포인트

    orderer_name: str  # 주문자 이름
    receiver: str  # 받는 사람
    receiver_phone: str  # 받는 사람 연락처
    zipcode: str  # 우편번호
    address1: str  # 기본 주소
    address2: Optional[str] = None  # 상세 주소
    request_memo: Optional[str] = None  # 배송 요청 사항

    ordered_at: datetime  # 주문 시각
    paid_at: Optional[datetime] = None  # 결제 시각
    delivered_at: Optional[datetime] = None  # 배송 완료 시각

    items: List[OrderItemResponse] = []  # 주문에 포함된 상품 목록
    payment: Optional[PaymentResponse] = None  # 결제 정보. 아직 없을 수 있다.
    shipment: Optional[ShipmentResponse] = None  # 배송 정보. 아직 없을 수 있다.
    is_cancelable: bool = False  # 현재 주문을 취소할 수 있는지 여부


class OrderCreateResponse(OrderResponse):
    """비회원 결제 인증 토큰을 포함할 수 있는 주문 생성 응답이다."""

    # 회원 주문에는 None이며, 비회원은 결제 단계에서 이 토큰을 제출한다.
    guest_order_token: Optional[str] = None


class OrderCancelRequest(BaseModel):
    """주문 취소를 요청할 때 받을 데이터."""

    reason_code: str = Field(
        "CHANGE_MIND",
        max_length=40,
    )  # 취소 사유 코드
    reason_text: Optional[str] = None  # 취소 사유 상세 내용


class PaymentConfirmRequest(BaseModel):
    """결제대행사(PG)가 결제 승인 결과를 전달할 때 받는 데이터."""

    order_no: str  # 주문 번호
    pg_tid: str  # PG 거래 번호
    amount: int  # 승인된 결제 금액
    result_code: str = "0000"  # 결제 결과 코드. 기본값은 성공 코드
    card_name: Optional[str] = None  # 카드사 이름
    card_no_masked: Optional[str] = None  # 일부를 가린 카드 번호


class InvoiceRegisterRequest(BaseModel):
    """관리자가 배송 정보를 등록할 때 받을 데이터."""

    carrier_code: str = Field("CJ", max_length=20)  # 택배사 코드
    carrier_name: str = Field("CJ대한통운", max_length=60)  # 택배사 이름
    invoice_no: str = Field(..., max_length=40)  # 필수 운송장 번호


class OrderStatusUpdateRequest(BaseModel):
    """관리자가 주문 상태를 변경할 때 받을 데이터."""

    status: str  # 변경할 주문 상태
    memo: Optional[str] = None  # 상태 변경 관련 메모


class GuestOrderLookupRequest(BaseModel):
    """비회원 주문번호와 주문 시 입력한 이메일을 본문으로 받는다."""

    order_no: str = Field(..., min_length=1, max_length=30)
    email: EmailStr
