"""장바구니와 위시리스트 ORM 모델."""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,  # 여러 열의 조합이 중복되지 않도록 제한
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from team_backend.app.core.database import Base


class Cart(Base):
    """회원 또는 비회원의 장바구니."""

    __tablename__ = "carts"
    __table_args__ = {"schema": "shop"}

    cart_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # 장바구니 번호

    # 로그인 회원의 장바구니라면 회원 번호를 저장한다.
    # 비회원 장바구니는 member_id가 비어 있을 수 있다.
    member_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("shop.members.member_id", ondelete="CASCADE"),
    )

    # 비회원의 장바구니를 구분할 때 사용하는 세션 식별값
    session_key: Mapped[Optional[str]] = mapped_column(String(64))

    # 장바구니 생성·수정 시각. 값이 없으면 DB가 현재 시각을 기록한다.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # 장바구니 안에 담긴 상품 목록
    # 장바구니가 삭제되면 연결된 상품 항목도 함께 삭제한다.
    # selectin은 상품 항목들을 별도 조회해 한 번에 불러오는 방식이다.
    items: Mapped[List["CartItem"]] = relationship(
        back_populates="cart",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def total_quantity(self) -> int:
        """선택된 상품들의 수량 합계를 계산한다."""
        # is_selected가 True인 상품만 주문할 수량에 포함한다.
        return sum(i.quantity for i in self.items if i.is_selected)


class CartItem(Base):
    """장바구니에 담긴 도서 한 종류와 수량."""

    __tablename__ = "cart_items"

    # 같은 장바구니에 같은 도서를 두 번 저장하지 못하게 한다.
    # 같은 책을 더 담으면 보통 기존 항목의 quantity를 늘린다.
    __table_args__ = (
        UniqueConstraint(
            "cart_id",
            "book_id",
            name="cart_items_cart_id_book_id_key",
        ),
        {"schema": "shop"},
    )

    cart_item_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # 장바구니 항목 번호

    # 이 항목이 속한 장바구니 번호
    # 장바구니가 삭제되면 항목도 DB에서 삭제한다.
    cart_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("shop.carts.cart_id", ondelete="CASCADE"),
    )

    # 장바구니에 담긴 도서 번호
    # 도서가 DB에서 삭제되면 이 항목도 삭제한다.
    book_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("shop.books.book_id", ondelete="CASCADE"),
    )

    quantity: Mapped[int] = mapped_column(Integer, default=1)  # 담은 수량
    is_selected: Mapped[bool] = mapped_column(Boolean, default=True)  # 주문 대상으로 선택했는지 여부
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # 이 항목이 속한 장바구니. Cart.items와 양방향으로 연결된다.
    cart: Mapped["Cart"] = relationship(back_populates="items")

    # 담긴 도서 정보를 함께 불러온다.
    book: Mapped["object"] = relationship("Book", lazy="joined")


class Wishlist(Base):
    """회원이 관심 상품으로 저장한 도서 목록."""

    __tablename__ = "wishlists"

    # 한 회원이 같은 책을 위시리스트에 중복 저장하지 못하게 한다.
    __table_args__ = (
        UniqueConstraint(
            "member_id",
            "book_id",
            name="wishlists_member_id_book_id_key",
        ),
        {"schema": "shop"},
    )

    wishlist_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # 위시리스트 항목 번호

    # 관심 도서를 등록한 회원 번호
    # 회원이 삭제되면 해당 회원의 위시리스트도 삭제한다.
    member_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("shop.members.member_id", ondelete="CASCADE"),
    )

    # 위시리스트에 저장한 도서 번호
    # 도서가 삭제되면 위시리스트 항목도 삭제한다.
    book_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("shop.books.book_id", ondelete="CASCADE"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )  # 위시리스트에 추가한 시각

    # 위시리스트에서 도서 정보를 조회할 때 도서 데이터도 함께 불러온다.
    book: Mapped["object"] = relationship("Book", lazy="joined")