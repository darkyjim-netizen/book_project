"""장바구니와 위시리스트 기능을 처리하는 서비스."""
import logging
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from team_backend.app.core.config import settings
from team_backend.app.core.exceptions import BusinessError, NotFoundError
from team_backend.app.models.book import Book
from team_backend.app.models.cart import Cart, CartItem, Wishlist
from team_backend.app.models.enums import BookStatus
from team_backend.app.models.member import Member
from team_backend.app.schemas.order import CartItemResponse, CartResponse

logger = logging.getLogger(__name__)


class CartService:
    """장바구니와 위시리스트의 DB 작업을 처리한다."""

    def __init__(self, db: Session):
        self.db = db  # 서비스 메서드에서 사용할 DB 세션

    # ------------------------------------------------------------------ 조회
    def get_or_create_cart(
        self,
        member: Optional[Member],
        session_key: Optional[str] = None,
    ) -> Cart:
        """회원 번호 또는 비회원 세션 키로 장바구니를 찾고, 없으면 만든다."""

        if member is not None:
            # 로그인 회원의 기존 장바구니를 찾는다.
            cart = self.db.scalar(
                select(Cart).where(Cart.member_id == member.member_id)
            )

            if cart is None:
                # 장바구니가 없으면 새로 만든다.
                cart = Cart(member_id=member.member_id)
                self.db.add(cart)
                self.db.commit()
                self.db.refresh(cart)

            return cart

        # 비회원은 장바구니를 구분할 세션 키가 필요하다.
        if not session_key:
            raise BusinessError(
                "세션 키가 필요합니다.",
                code="SESSION_REQUIRED",
            )

        # 해당 세션 키에 연결된 비회원 장바구니를 찾는다.
        cart = self.db.scalar(
            select(Cart).where(Cart.session_key == session_key)
        )

        if cart is None:
            # 없으면 현재 세션 키로 새 장바구니를 만든다.
            cart = Cart(session_key=session_key)
            self.db.add(cart)
            self.db.commit()
            self.db.refresh(cart)

        return cart

    def _load_items(self, cart_id: int) -> List[CartItem]:
        """장바구니 항목과 각 도서의 저자 정보를 불러온다."""

        return list(
            self.db.scalars(
                select(CartItem)
                # 장바구니 항목을 조회할 때 도서와 저자 관계도 함께 불러온다.
                .options(
                    selectinload(CartItem.book).selectinload(Book.book_authors)
                )
                .where(CartItem.cart_id == cart_id)
                .order_by(CartItem.created_at.desc())
            ).unique()
        )

    def build_response(
        self,
        cart: Cart,
        member: Optional[Member] = None,
    ) -> CartResponse:
        """장바구니 항목을 응답 형식으로 바꾸고 금액을 계산한다."""

        items = self._load_items(cart.cart_id)
        item_responses: List[CartItemResponse] = []

        item_amount = 0.0  # 선택한 상품들의 판매가 합계
        list_amount = 0.0  # 선택한 상품들의 정가 합계
        selected_count = 0  # 선택된 상품 종류 수

        for item in items:
            book: Book = item.book

            # 이 상품 항목의 판매가 합계
            total = float(book.sale_price) * item.quantity

            if item.is_selected:
                # 선택된 항목만 결제 예정 금액과 할인 계산에 포함한다.
                item_amount += total
                list_amount += float(book.list_price) * item.quantity
                selected_count += 1

            # 상품 선택 여부와 관계없이 장바구니의 모든 항목을 응답에 담는다.
            item_responses.append(
                CartItemResponse(
                    cart_item_id=item.cart_item_id,
                    book_id=book.book_id,
                    title=book.title,
                    cover_image=book.cover_image,
                    authors=book.author_names,
                    unit_price=float(book.sale_price),
                    list_price=float(book.list_price),
                    quantity=item.quantity,
                    item_total=total,
                    is_selected=item.is_selected,
                    stock_qty=book.stock_qty,
                    status=book.status.value,
                    # 판매 가능 상태이고 요청 수량만큼 재고가 있어야 구매 가능하다.
                    is_available=(
                        book.is_available
                        and book.stock_qty >= item.quantity
                    ),
                )
            )

        # 회원 등급에 무료 배송 기준이 있으면 사용하고,
        # 비회원이거나 등급 정보가 없으면 공통 설정값을 사용한다.
        free_limit = (
            float(member.grade.free_ship_limit)
            if member is not None and member.grade is not None
            else float(settings.FREE_SHIP_LIMIT)
        )

        # 선택 상품이 없거나 무료 배송 기준 이상이면 배송비는 0원이다.
        ship_fee = (
            0.0
            if item_amount >= free_limit or item_amount == 0
            else float(settings.DEFAULT_SHIP_FEE)
        )

        # 회원 등급별 적립률이 있으면 적용하고, 아니면 기본 적립률을 쓴다.
        point_rate = (
            float(member.grade.point_rate) / 100.0
            if member is not None and member.grade is not None
            else settings.POINT_SAVE_RATE
        )

        # 선택 상품 금액에 적립률을 곱해 예상 포인트를 계산한다.
        expected_point = int(item_amount * point_rate)

        return CartResponse(
            cart_id=cart.cart_id,
            items=item_responses,
            selected_count=selected_count,
            item_amount=item_amount,
            # 정가 합계와 판매가 합계의 차이를 할인액으로 본다.
            discount_amount=max(list_amount - item_amount, 0),
            ship_fee=ship_fee,
            expected_point=expected_point,
            total_amount=item_amount + ship_fee,
        )

    # ------------------------------------------------------------------ 변경
    def add_item(
        self,
        cart: Cart,
        book_id: int,
        quantity: int,
    ) -> CartItem:
        """도서를 장바구니에 넣는다. 이미 있으면 수량을 더한다."""

        book = self.db.get(Book, book_id)

        # 도서가 없거나 논리 삭제 상태면 추가할 수 없다.
        if book is None or book.status == BookStatus.DELETED:
            raise NotFoundError("도서를 찾을 수 없습니다.")

        if book.status == BookStatus.STOP:
            raise BusinessError("판매가 중지된 도서입니다.")

        # 현재 장바구니에 담긴 상품 종류 수를 센다.
        count = self.db.scalar(
            select(func.count())
            .select_from(CartItem)
            .where(CartItem.cart_id == cart.cart_id)
        )

        # 장바구니에 담을 수 있는 상품 종류 수를 제한한다.
        if (count or 0) >= settings.CART_MAX_ITEMS:
            raise BusinessError(
                f"장바구니에는 최대 {settings.CART_MAX_ITEMS}종까지 담을 수 있습니다."
            )

        # 같은 도서가 이미 장바구니에 있는지 확인한다.
        item = self.db.scalar(
            select(CartItem).where(
                CartItem.cart_id == cart.cart_id,
                CartItem.book_id == book_id,
            )
        )

        if item is None:
            # 처음 담는 도서면 새 항목을 만든다.
            item = CartItem(
                cart_id=cart.cart_id,
                book_id=book_id,
                quantity=quantity,
            )
            self.db.add(item)
        else:
            # 이미 담은 도서면 수량을 더하되 최대 99개로 제한한다.
            item.quantity = min(item.quantity + quantity, 99)

        # 예약 판매가 아니고 요청 수량보다 재고가 적으면 추가를 거부한다.
        if book.stock_qty < item.quantity and book.status != BookStatus.PREORDER:
            raise BusinessError(
                f"재고가 부족합니다. (현재 재고 {book.stock_qty}권)",
                code="OUT_OF_STOCK",
            )

        self.db.commit()
        self.db.refresh(item)
        return item

    def update_item(
        self,
        cart: Cart,
        cart_item_id: int,
        quantity: Optional[int],
        is_selected: Optional[bool],
    ) -> CartItem:
        """장바구니 항목의 수량이나 선택 여부를 변경한다."""

        # cart_id 조건도 확인해 다른 사람의 항목을 수정하지 못하게 한다.
        item = self.db.scalar(
            select(CartItem).where(
                CartItem.cart_item_id == cart_item_id,
                CartItem.cart_id == cart.cart_id,
            )
        )
        if item is None:
            raise NotFoundError("장바구니 항목을 찾을 수 없습니다.")

        if quantity is not None:
            book = self.db.get(Book, item.book_id)

            # 예약 판매가 아니면 변경할 수량만큼 재고가 있는지 확인한다.
            if (
                book
                and book.stock_qty < quantity
                and book.status != BookStatus.PREORDER
            ):
                raise BusinessError(
                    f"재고가 부족합니다. (현재 재고 {book.stock_qty}권)",
                    code="OUT_OF_STOCK",
                )

            item.quantity = quantity

        # None이 아닐 때만 선택 상태를 바꾼다.
        if is_selected is not None:
            item.is_selected = is_selected

        self.db.commit()
        self.db.refresh(item)
        return item

    def remove_item(self, cart: Cart, cart_item_id: int) -> None:
        """회원의 장바구니에서 지정한 항목 하나를 삭제한다."""

        deleted = (
            self.db.query(CartItem)
            .filter(
                CartItem.cart_item_id == cart_item_id,
                CartItem.cart_id == cart.cart_id,
            )
            .delete()
        )

        # 삭제된 항목이 없으면 번호가 잘못됐거나 이 장바구니 소유가 아니다.
        if not deleted:
            raise NotFoundError("장바구니 항목을 찾을 수 없습니다.")

        self.db.commit()

    def remove_items(
        self,
        cart: Cart,
        cart_item_ids: List[int],
    ) -> int:
        """지정한 항목 여러 개를 한 번에 삭제하고 삭제 수를 반환한다."""

        deleted = (
            self.db.query(CartItem)
            .filter(
                CartItem.cart_id == cart.cart_id,
                CartItem.cart_item_id.in_(cart_item_ids),
            )
            .delete(synchronize_session=False)
        )
        self.db.commit()
        return deleted

    def clear(self, cart: Cart, only_selected: bool = False) -> int:
        """장바구니 전체 또는 선택된 항목만 삭제한다."""

        query = self.db.query(CartItem).filter(
            CartItem.cart_id == cart.cart_id
        )

        if only_selected:
            # 선택된 항목만 지우도록 조건을 추가한다.
            query = query.filter(CartItem.is_selected == True)  # noqa: E712

        deleted = query.delete(synchronize_session=False)
        self.db.commit()
        return deleted

    def select_all(self, cart: Cart, selected: bool) -> int:
        """장바구니 항목 전체를 선택하거나 선택 해제한다."""

        updated = (
            self.db.query(CartItem)
            .filter(CartItem.cart_id == cart.cart_id)
            .update(
                {CartItem.is_selected: selected},
                synchronize_session=False,
            )
        )
        self.db.commit()
        return updated  # 변경된 항목 수

    def merge_session_cart(self, member: Member, session_key: str) -> None:
        """비회원 장바구니의 상품을 로그인 회원 장바구니에 합친다."""

        guest = self.db.scalar(
            select(Cart).where(Cart.session_key == session_key)
        )
        if guest is None:
            return  # 병합할 비회원 장바구니가 없다.

        target = self.get_or_create_cart(member)

        for item in self._load_items(guest.cart_id):
            # 회원 장바구니에 같은 도서가 있는지 확인한다.
            exists = self.db.scalar(
                select(CartItem).where(
                    CartItem.cart_id == target.cart_id,
                    CartItem.book_id == item.book_id,
                )
            )

            if exists:
                # 이미 있으면 수량을 더하되 최대 99개로 제한한다.
                exists.quantity = min(exists.quantity + item.quantity, 99)
            else:
                # 없으면 회원 장바구니에 새 항목으로 추가한다.
                self.db.add(
                    CartItem(
                        cart_id=target.cart_id,
                        book_id=item.book_id,
                        quantity=item.quantity,
                    )
                )

        # 병합이 끝난 비회원 장바구니를 삭제한다.
        self.db.delete(guest)
        self.db.commit()

        logger.info(
            "비회원 장바구니 병합 완료: member_id=%s",
            member.member_id,
        )

    # ---------------------------------------------------------------- 위시리스트
    def toggle_wishlist(self, member: Member, book_id: int) -> bool:
        """위시리스트에 있으면 삭제하고, 없으면 추가한다."""

        if self.db.get(Book, book_id) is None:
            raise NotFoundError("도서를 찾을 수 없습니다.")

        existing = self.db.scalar(
            select(Wishlist).where(
                Wishlist.member_id == member.member_id,
                Wishlist.book_id == book_id,
            )
        )

        if existing:
            # 이미 저장된 도서라면 위시리스트에서 제거한다.
            self.db.delete(existing)
            self.db.commit()
            return False

        # 저장되어 있지 않으면 새로 추가한다.
        self.db.add(
            Wishlist(
                member_id=member.member_id,
                book_id=book_id,
            )
        )
        self.db.commit()
        return True

    def list_wishlist(
        self,
        member: Member,
        page: int = 1,
        size: int = 20,
    ):
        """회원 위시리스트를 최신 등록순으로 페이지 조회한다."""

        # 페이지 제한을 적용하지 않은 전체 위시리스트 항목 수
        total = (
            self.db.scalar(
                select(func.count())
                .select_from(Wishlist)
                .where(Wishlist.member_id == member.member_id)
            )
            or 0
        )

        # 위시리스트 항목과 도서·저자 정보를 함께 가져온다.
        rows = list(
            self.db.scalars(
                select(Wishlist)
                .options(
                    selectinload(Wishlist.book).selectinload(Book.book_authors)
                )
                .where(Wishlist.member_id == member.member_id)
                .order_by(Wishlist.created_at.desc())
                .offset((page - 1) * size)
                .limit(size)
            ).unique()
        )

        return rows, total