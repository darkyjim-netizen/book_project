from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


# 주문자, 배송지, 구매 항목과 주문 당시 금액을 저장하는 테이블입니다.
class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    # 회원이 탈퇴해도 주문 기록은 남기고 회원 연결만 비웁니다.
    member_id: Mapped[int | None] = mapped_column(ForeignKey("members.id", ondelete="SET NULL"), index=True)
    receiver_name: Mapped[str] = mapped_column(String(100))
    address: Mapped[str] = mapped_column(String(500))
    # 주문 당시의 상품 정보를 JSON으로 저장하여 이후 상품 변경과 분리합니다.
    items: Mapped[list[dict]] = mapped_column(JSON)
    total: Mapped[int] = mapped_column(BigInteger)
    region: Mapped[str | None] = mapped_column(String(40))
    age_group: Mapped[str | None] = mapped_column(String(20))
    # 새 주문의 기본 결제 상태를 테스트 결제 완료로 지정합니다.
    payment_status: Mapped[str] = mapped_column(String(20), default="test_paid")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
