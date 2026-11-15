from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


# 도서를 분류할 카테고리 이름을 저장하는 테이블입니다.
class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
