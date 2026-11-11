from datetime import datetime
from enum import Enum

from sqlalchemy import BigInteger, DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


# 주문이 거치는 상태를 정의합니다. 값은 DB에 문자열로 저장됩니다.
class OrderStatus(str, Enum):
    PENDING = "pending"            # 주문 대기 (결제 전)
    PAYMENT_WAIT = "payment_wait"  # 결제 진행 중
    PAID = "paid"                  # 결제 완료
    PREPARING = "preparing"        # 상품 준비 중
    SHIPPED = "shipped"            # 배송 중
    DELIVERED = "delivered"        # 배송 완료
    CANCELLED = "cancelled"        # 주문 취소
    REFUNDED = "refunded"          # 환불 완료


# 주문자, 배송지, 구매 항목과 주문 당시 금액을 저장하는 테이블입니다.
class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    # PG사에 전달하는 주문번호입니다. 결제 연동 이전에 만든 주문은 비어 있을 수 있습니다.
    order_number: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    # 회원이 탈퇴해도 주문 기록은 남기고 회원 연결만 비웁니다.
    member_id: Mapped[int | None] = mapped_column(ForeignKey("members.id", ondelete="SET NULL"), index=True)
    receiver_name: Mapped[str] = mapped_column(String(100))
    address: Mapped[str] = mapped_column(String(500))
    # 주문 당시의 상품 정보를 JSON으로 저장하여 이후 상품 변경과 분리합니다.
    items: Mapped[list[dict]] = mapped_column(JSON)
    total: Mapped[int] = mapped_column(BigInteger)
    region: Mapped[str | None] = mapped_column(String(40))
    age_group: Mapped[str | None] = mapped_column(String(20))
    # 주문 상태(OrderStatus 값)입니다. 상태 변경은 OrderService.transition_order_status로만 합니다.
    status: Mapped[str] = mapped_column(String(20), default=OrderStatus.PENDING.value,
                                        server_default=OrderStatus.PENDING.value, index=True)
    # 결제 방식입니다. test는 테스트 결제, toss는 토스페이먼츠 결제입니다.
    payment_method: Mapped[str] = mapped_column(String(20), default="test", server_default="test")
    # PG사 결제 키입니다. 결제 승인이 끝난 뒤에만 저장됩니다.
    payment_key: Mapped[str | None] = mapped_column(String(200))
    # 기존 응답과의 호환을 위해 유지합니다. 테스트 결제는 test_paid, 그 외에는 status와 같은 값을 가집니다.
    payment_status: Mapped[str] = mapped_column(String(20), default="test_paid")
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# 주문 상태가 바뀔 때마다 이전 상태, 새 상태, 사유를 남기는 이력 테이블입니다.
class OrderStatusHistory(Base):
    __tablename__ = "order_status_histories"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    # 상태를 바꾼 회원입니다. 회원이 탈퇴하면 연결만 비웁니다.
    changed_by: Mapped[int | None] = mapped_column(ForeignKey("members.id", ondelete="SET NULL"))
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
