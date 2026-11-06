from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int | None] = mapped_column(ForeignKey("members.id", ondelete="SET NULL"), index=True)
    receiver_name: Mapped[str] = mapped_column(String(100))
    address: Mapped[str] = mapped_column(String(500))
    items: Mapped[list[dict]] = mapped_column(JSON)
    total: Mapped[int] = mapped_column(BigInteger)
    region: Mapped[str | None] = mapped_column(String(40))
    age_group: Mapped[str | None] = mapped_column(String(20))
    payment_status: Mapped[str] = mapped_column(String(20), default="test_paid")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
