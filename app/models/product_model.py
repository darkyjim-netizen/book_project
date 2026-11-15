from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


# 도서 정보와 가격, 재고, 판매 상태를 저장하는 테이블입니다.
class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    author: Mapped[str] = mapped_column(String(200))
    price: Mapped[int]
    stock: Mapped[int]
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)
    # 판매 중 여부를 저장하여 실제 삭제 없이 도서를 목록에서 숨길 수 있게 합니다.
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


# 도서별 리뷰 본문을 저장하는 테이블입니다.
class Review(Base):
    __tablename__ = "product_reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    body: Mapped[str] = mapped_column(Text)
