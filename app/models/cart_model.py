from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


# 회원별 장바구니에 담긴 상품과 수량을 저장하는 테이블입니다.
class CartItem(Base):
    __tablename__ = "cart_items"
    # 같은 회원의 장바구니에 동일 상품이 중복 행으로 저장되지 않게 제한합니다.
    __table_args__ = (UniqueConstraint("member_id", "product_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[int]
