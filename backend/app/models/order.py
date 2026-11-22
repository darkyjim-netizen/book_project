"""주문, 결제, 환불, 배송 정보를 저장하는 ORM 모델."""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum as PgEnum,  # PostgreSQL ENUM 타입
    ForeignKey,      # 다른 테이블의 열을 참조
    Integer,
    Numeric,         # 금액처럼 정밀한 숫자
    SmallInteger,
    String,
    Text,
    func,            # now() 같은 DB 함수
)
from sqlalchemy.dialects.postgresql import JSONB  # PostgreSQL의 JSON 저장 타입
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import OrderStatus, PaymentMethod, PaymentStatus, ShipmentStatus


class Order(Base):
    """주문 한 건의 기본 정보와 결제·배송 관련 금액을 저장한다."""

    __tablename__ = "orders"
    __table_args__ = {"schema": "shop"}

    order_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # 내부 주문 번호
    order_no: Mapped[str] = mapped_column(
        String(30),
        unique=True,     # 외부에 보여줄 주문 번호는 중복될 수 없다.
        nullable=False,
    )

    # 비회원 주문도 가능하도록 회원 번호는 비어 있을 수 있다.
    member_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("shop.members.member_id"),
    )

    orderer_name: Mapped[str] = mapped_column(String(60), nullable=False)  # 주문자 이름
    orderer_phone: Mapped[str] = mapped_column(String(20), nullable=False)  # 주문자 전화번호
    orderer_email: Mapped[str] = mapped_column(String(190), nullable=False)  # 주문자 이메일

    # 주문 진행 상태. 값은 PostgreSQL에 미리 만든 order_status ENUM을 사용한다.
    status: Mapped[OrderStatus] = mapped_column(
        PgEnum(OrderStatus, name="order_status", schema="shop", create_type=False),
        default=OrderStatus.PENDING,  # 기본 상태는 결제 대기
    )

    item_amount: Mapped[float] = mapped_column(Numeric(12, 0), default=0)  # 상품 금액 합계
    discount_amount: Mapped[float] = mapped_column(Numeric(12, 0), default=0)  # 전체 할인 금액
    coupon_amount: Mapped[float] = mapped_column(Numeric(12, 0), default=0)  # 쿠폰 할인 금액
    point_used: Mapped[float] = mapped_column(Numeric(12, 0), default=0)  # 사용한 포인트
    ship_fee: Mapped[float] = mapped_column(Numeric(10, 0), default=0)  # 배송비
    total_amount: Mapped[float] = mapped_column(Numeric(12, 0), default=0)  # 최종 결제 금액
    point_saved: Mapped[float] = mapped_column(Numeric(10, 0), default=0)  # 적립될 포인트

    # 주문 시점의 배송 정보를 저장한다.
    receiver: Mapped[str] = mapped_column(String(60), nullable=False)  # 받는 사람
    receiver_phone: Mapped[str] = mapped_column(String(20), nullable=False)  # 받는 사람 연락처
    zipcode: Mapped[str] = mapped_column(String(10), nullable=False)  # 우편번호
    address1: Mapped[str] = mapped_column(String(255), nullable=False)  # 기본 주소
    address2: Mapped[Optional[str]] = mapped_column(String(255))  # 상세 주소
    request_memo: Mapped[Optional[str]] = mapped_column(String(255))  # 배송 요청 사항
    is_gift_wrap: Mapped[bool] = mapped_column(Boolean, default=False)  # 선물 포장 요청 여부

    # 주문 및 처리 시각
    ordered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )  # 주문 생성 시각
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))  # 결제 완료 시각
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))  # 배송 완료 시각
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))  # 구매 확정 시각
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))  # 취소 시각
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )  # 주문 정보 생성 시각 또는 갱신 시각

    # 한 주문에는 여러 상품 항목이 들어갈 수 있다.
    # 주문이 삭제되면 연결된 상품 항목도 함께 삭제한다.
    items: Mapped[List["OrderItem"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # 한 주문에 결제 기록이 여러 개 연결될 수 있다.
    payments: Mapped[List["Payment"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # 한 주문에 배송 기록이 여러 개 연결될 수 있다.
    shipments: Mapped[List["Shipment"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def is_cancelable(self) -> bool:
        """현재 상태에서 주문 취소가 가능한지 확인한다."""
        return self.status in (
            OrderStatus.PENDING,
            OrderStatus.PAID,
            OrderStatus.PREPARING,
        )

    @property
    def main_payment(self) -> Optional["Payment"]:
        """결제 완료된 결제가 있으면 우선 반환하고, 없으면 첫 결제를 반환한다."""
        paid = [p for p in self.payments if p.status == PaymentStatus.PAID]
        return paid[0] if paid else (self.payments[0] if self.payments else None)

    @property
    def summary_title(self) -> str:
        """주문 목록에 표시할 대표 상품명을 만든다."""
        if not self.items:
            return "주문 상품 없음"

        # 첫 번째 주문 상품의 이름을 대표 이름으로 사용한다.
        first = self.items[0].book_title

        if len(self.items) == 1:
            return first

        # 상품 종류가 여러 개면 첫 상품명과 나머지 종류 수를 표시한다.
        return f"{first} 외 {len(self.items) - 1}건"


class OrderItem(Base):
    """주문에 포함된 도서 한 종류의 가격과 수량."""

    __tablename__ = "order_items"
    __table_args__ = {"schema": "shop"}

    order_item_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # 주문 상품 번호

    # 이 항목이 속한 주문. 주문이 삭제되면 항목도 삭제된다.
    order_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("shop.orders.order_id", ondelete="CASCADE"),
    )

    # 주문한 도서 번호
    book_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("shop.books.book_id"),
    )

    # 주문 당시의 제목을 저장해 둔다.
    # 나중에 도서 제목이 바뀌어도 과거 주문 내역에는 주문 당시 제목이 남는다.
    book_title: Mapped[str] = mapped_column(String(300), nullable=False)

    unit_price: Mapped[float] = mapped_column(Numeric(10, 0), nullable=False)  # 주문 당시 한 권 가격
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)  # 주문 수량
    item_discount: Mapped[float] = mapped_column(Numeric(10, 0), default=0)  # 해당 상품 할인액
    item_total: Mapped[float] = mapped_column(Numeric(12, 0), nullable=False)  # 이 상품 항목의 합계

    # 주문 전체 상태와 별도로 상품 항목별 상태도 저장한다.
    status: Mapped[OrderStatus] = mapped_column(
        PgEnum(OrderStatus, name="order_status", schema="shop", create_type=False),
        default=OrderStatus.PENDING,
    )

    is_reviewed: Mapped[bool] = mapped_column(Boolean, default=False)  # 리뷰 작성 여부
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # 이 상품 항목이 속한 주문
    order: Mapped["Order"] = relationship(back_populates="items")

    # 주문한 도서 정보를 함께 불러온다.
    book: Mapped["object"] = relationship("Book", lazy="joined")


class Payment(Base):
    """결제 요청과 결과를 저장하는 테이블."""

    __tablename__ = "payments"
    __table_args__ = {"schema": "shop"}

    payment_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # 결제 번호

    # 이 결제가 연결된 주문. 주문이 삭제되면 결제 기록도 삭제된다.
    order_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("shop.orders.order_id", ondelete="CASCADE"),
    )

    pg_provider: Mapped[str] = mapped_column(String(30), default="INICIS")  # 결제대행사 이름
    pg_tid: Mapped[Optional[str]] = mapped_column(String(100))  # 결제대행사가 발급한 거래 번호

    # 결제 수단과 결과 상태를 PostgreSQL ENUM으로 저장한다.
    method: Mapped[PaymentMethod] = mapped_column(
        PgEnum(PaymentMethod, name="payment_method", schema="shop", create_type=False)
    )
    status: Mapped[PaymentStatus] = mapped_column(
        PgEnum(PaymentStatus, name="payment_status", schema="shop", create_type=False),
        default=PaymentStatus.READY,
    )

    amount: Mapped[float] = mapped_column(Numeric(12, 0), nullable=False)  # 결제 요청 금액
    cancelled_amount: Mapped[float] = mapped_column(Numeric(12, 0), default=0)  # 취소된 금액

    card_name: Mapped[Optional[str]] = mapped_column(String(60))  # 카드사 또는 카드 이름
    card_no_masked: Mapped[Optional[str]] = mapped_column(String(30))  # 일부를 가린 카드 번호
    install_month: Mapped[int] = mapped_column(SmallInteger, default=0)  # 할부 개월 수

    vbank_bank: Mapped[Optional[str]] = mapped_column(String(60))  # 가상계좌 은행
    vbank_no: Mapped[Optional[str]] = mapped_column(String(40))  # 가상계좌 번호
    vbank_holder: Mapped[Optional[str]] = mapped_column(String(60))  # 가상계좌 예금주
    vbank_due: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))  # 가상계좌 입금 기한

    receipt_url: Mapped[Optional[str]] = mapped_column(String(255))  # 결제 영수증 주소
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )  # 결제 요청 시각
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))  # 결제 승인 시각
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))  # 결제 취소 시각

    # 이 결제가 연결된 주문
    order: Mapped["Order"] = relationship(back_populates="payments")


class PaymentLog(Base):
    """결제대행사와 주고받은 요청·응답 기록을 저장하는 로그 테이블."""

    __tablename__ = "payment_logs"
    __table_args__ = {"schema": "log"}

    log_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # 로그 번호
    payment_id: Mapped[Optional[int]] = mapped_column(BigInteger)  # 관련 결제 번호
    order_no: Mapped[Optional[str]] = mapped_column(String(30))  # 관련 주문 번호
    action: Mapped[str] = mapped_column(String(40), nullable=False)  # 결제 승인·취소 등 작업 종류

    # JSON 형태의 요청과 응답 데이터를 저장한다.
    request_body: Mapped[Optional[dict]] = mapped_column(JSONB)
    response_body: Mapped[Optional[dict]] = mapped_column(JSONB)

    result_code: Mapped[Optional[str]] = mapped_column(String(50))  # 결제대행사의 처리 결과 코드
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class Refund(Base):
    """환불 요청과 처리 결과를 저장하는 테이블."""

    __tablename__ = "refunds"
    __table_args__ = {"schema": "shop"}

    refund_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # 환불 번호
    order_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("shop.orders.order_id"),
    )  # 환불 대상 주문

    # 환불이 특정 결제와 연결되면 결제 번호를 기록한다.
    payment_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("shop.payments.payment_id"),
    )

    refund_amount: Mapped[float] = mapped_column(Numeric(12, 0), nullable=False)  # 환불 금액
    point_restore: Mapped[float] = mapped_column(Numeric(10, 0), default=0)  # 복원할 포인트
    reason_code: Mapped[str] = mapped_column(String(40), nullable=False)  # 환불 사유 분류
    reason_text: Mapped[Optional[str]] = mapped_column(Text)  # 환불 사유 상세 설명
    processed_by: Mapped[Optional[int]] = mapped_column(BigInteger)  # 처리한 관리자 또는 직원 번호

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )  # 환불 요청이 생성된 시각
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))  # 환불 완료 시각


class Shipment(Base):
    """주문 상품의 배송 정보를 저장하는 테이블."""

    __tablename__ = "shipments"
    __table_args__ = {"schema": "shop"}

    shipment_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # 배송 번호

    # 이 배송이 연결된 주문. 주문이 삭제되면 배송 정보도 삭제된다.
    order_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("shop.orders.order_id", ondelete="CASCADE"),
    )

    carrier_code: Mapped[str] = mapped_column(String(20), default="CJ")  # 택배사 코드
    carrier_name: Mapped[str] = mapped_column(String(60), default="CJ대한통운")  # 택배사 이름
    invoice_no: Mapped[Optional[str]] = mapped_column(String(40))  # 운송장 번호

    # 배송 진행 상태
    status: Mapped[ShipmentStatus] = mapped_column(
        PgEnum(ShipmentStatus, name="shipment_status", schema="shop", create_type=False),
        default=ShipmentStatus.READY,
    )

    ship_fee: Mapped[float] = mapped_column(Numeric(10, 0), default=0)  # 배송비
    shipped_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))  # 발송 시각
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))  # 배송 완료 시각
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # 이 배송이 속한 주문
    order: Mapped["Order"] = relationship(back_populates="shipments")

    # 배송 상태가 바뀔 때마다 남기는 배송 이력 목록
    tracking: Mapped[List["ShipmentTracking"]] = relationship(
        back_populates="shipment",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ShipmentTracking(Base):
    """배송 상태가 바뀐 시각과 위치를 기록하는 테이블."""

    __tablename__ = "shipment_tracking"
    __table_args__ = {"schema": "shop"}

    tracking_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # 배송 이력 번호

    # 이 이력이 속한 배송. 배송이 삭제되면 이력도 삭제된다.
    shipment_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("shop.shipments.shipment_id", ondelete="CASCADE"),
    )

    # 이 시점의 배송 상태
    status: Mapped[ShipmentStatus] = mapped_column(
        PgEnum(ShipmentStatus, name="shipment_status", schema="shop", create_type=False)
    )

    location: Mapped[Optional[str]] = mapped_column(String(120))  # 배송 처리 위치
    description: Mapped[Optional[str]] = mapped_column(String(255))  # 상태에 대한 설명
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )  # 배송 상태가 발생한 시각

    # 이 배송 이력이 속한 배송 정보
    shipment: Mapped["Shipment"] = relationship(back_populates="tracking")