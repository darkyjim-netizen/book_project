"""주문 생성, 조회, 상태 변경, 취소·환불을 처리하는 서비스."""
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, selectinload

from team_backend.app.core.config import settings
from team_backend.app.core.exceptions import BusinessError, NotFoundError
from team_backend.app.models.book import Book, StockHistory
from team_backend.app.models.cart import CartItem
from team_backend.app.models.enums import (
    BookStatus,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    PointReason,
    ShipmentStatus,
)
from team_backend.app.models.member import Member, PointHistory
from team_backend.app.models.order import (
    Order,
    OrderItem,
    Payment,
    Refund,
    Shipment,
    ShipmentTracking,
)
from team_backend.app.models.promotion import MemberCoupon
from team_backend.app.schemas.order import (
    OrderCreateRequest,
    OrderItemResponse,
    OrderResponse,
    PaymentResponse,
    ShipmentResponse,
    TrackingResponse,
)

# 주문 처리 과정에서 중요한 내용을 로그로 남길 때 사용한다.
logger = logging.getLogger(__name__)


# 주문 상태를 화면에 표시할 한국어 문구로 바꿔 준다.
STATUS_LABELS = {
    OrderStatus.PENDING: "입금/결제 대기",
    OrderStatus.PAID: "결제 완료",
    OrderStatus.PREPARING: "상품 준비 중",
    OrderStatus.SHIPPING: "배송 중",
    OrderStatus.DELIVERED: "배송 완료",
    OrderStatus.CONFIRMED: "구매 확정",
    OrderStatus.CANCELLED: "주문 취소",
    OrderStatus.RETURN_REQ: "반품 접수",
    OrderStatus.RETURNED: "반품 완료",
    OrderStatus.EXCHANGE_REQ: "교환 접수",
    OrderStatus.EXCHANGED: "교환 완료",
}


# 현재 주문 상태에서 다음에 이동할 수 있는 상태를 정해 둔다.
# 예: 결제 완료(PAID) 상태에서는 상품 준비(PREPARING) 또는 취소(CANCELLED) 가능
ALLOWED_TRANSITIONS = {
    OrderStatus.PENDING: {OrderStatus.PAID, OrderStatus.CANCELLED},
    OrderStatus.PAID: {OrderStatus.PREPARING, OrderStatus.CANCELLED},
    OrderStatus.PREPARING: {OrderStatus.SHIPPING, OrderStatus.CANCELLED},
    OrderStatus.SHIPPING: {OrderStatus.DELIVERED, OrderStatus.RETURN_REQ},
    OrderStatus.DELIVERED: {
        OrderStatus.CONFIRMED,
        OrderStatus.RETURN_REQ,
        OrderStatus.EXCHANGE_REQ,
    },
    OrderStatus.CONFIRMED: set(),  # 구매 확정 뒤에는 다른 상태로 바꿀 수 없다.
    OrderStatus.RETURN_REQ: {OrderStatus.RETURNED, OrderStatus.DELIVERED},
    OrderStatus.EXCHANGE_REQ: {OrderStatus.EXCHANGED, OrderStatus.DELIVERED},
}


class OrderService:
    """주문과 관련된 DB 처리 및 업무 규칙을 담당한다."""

    def __init__(self, db: Session):
        self.db = db  # 이 서비스에서 사용할 DB 세션

    # ------------------------------------------------------------------ 응답 변환
    def to_response(self, order: Order) -> OrderResponse:
        """주문 DB 객체를 API 응답 형식으로 바꾼다."""

        # 주문과 연결된 결제 정보와 배송 정보를 가져온다.
        payment = order.main_payment
        shipment = order.shipments[0] if order.shipments else None

        # 주문 상품을 API 응답에 넣을 수 있는 형태로 하나씩 변환한다.
        items = []
        for item in order.items:
            # 연결된 도서가 있으면 표지 이미지를 가져온다.
            cover = item.book.cover_image if item.book else None

            items.append(
                OrderItemResponse(
                    order_item_id=item.order_item_id,
                    book_id=item.book_id,
                    book_title=item.book_title,
                    cover_image=cover,
                    unit_price=float(item.unit_price),
                    quantity=item.quantity,
                    item_discount=float(item.item_discount),
                    item_total=float(item.item_total),
                    status=item.status.value,
                    is_reviewed=item.is_reviewed,
                )
            )

        # 배송 정보가 있을 때만 배송 응답 객체를 만든다.
        shipment_res = None
        if shipment:
            shipment_res = ShipmentResponse(
                shipment_id=shipment.shipment_id,
                carrier_code=shipment.carrier_code,
                carrier_name=shipment.carrier_name,
                invoice_no=shipment.invoice_no,
                status=shipment.status.value,
                shipped_at=shipment.shipped_at,
                delivered_at=shipment.delivered_at,
                # 배송 추적 기록을 발생 시간 순서대로 정렬해 응답에 넣는다.
                tracking=[
                    TrackingResponse(
                        status=t.status.value,
                        location=t.location,
                        description=t.description,
                        occurred_at=t.occurred_at,
                    )
                    for t in sorted(
                        shipment.tracking,
                        key=lambda x: x.occurred_at,
                    )
                ],
            )

        # 화면에서 사용할 주문 전체 정보를 응답 객체에 담는다.
        return OrderResponse(
            order_id=order.order_id,
            order_no=order.order_no,
            status=order.status.value,
            # 상태에 맞는 한국어 설명을 찾고, 없으면 상태값 자체를 사용한다.
            status_label=STATUS_LABELS.get(order.status, order.status.value),
            summary_title=order.summary_title,
            item_amount=float(order.item_amount),
            discount_amount=float(order.discount_amount),
            coupon_amount=float(order.coupon_amount),
            point_used=float(order.point_used),
            ship_fee=float(order.ship_fee),
            total_amount=float(order.total_amount),
            point_saved=float(order.point_saved),
            orderer_name=order.orderer_name,
            receiver=order.receiver,
            receiver_phone=order.receiver_phone,
            zipcode=order.zipcode,
            address1=order.address1,
            address2=order.address2,
            request_memo=order.request_memo,
            ordered_at=order.ordered_at,
            paid_at=order.paid_at,
            delivered_at=order.delivered_at,
            items=items,
            # 결제 정보가 있을 때만 Pydantic 응답 객체로 변환한다.
            payment=PaymentResponse.model_validate(payment) if payment else None,
            shipment=shipment_res,
            is_cancelable=order.is_cancelable,
        )

    # ------------------------------------------------------------------ 주문 생성
    def _resolve_items(
        self,
        member: Optional[Member],
        payload: OrderCreateRequest,
    ) -> List[Tuple[Book, int]]:
        """요청에서 주문할 도서와 수량을 찾아 목록으로 만든다."""

        pairs: List[Tuple[Book, int]] = []

        # 요청에 상품 목록이 직접 들어 있으면 그 목록으로 주문한다.
        if payload.items:
            for req in payload.items:
                book = self.db.get(Book, req.book_id)

                # 요청한 도서가 DB에 없으면 주문을 진행할 수 없다.
                if book is None:
                    raise NotFoundError(
                        f"도서를 찾을 수 없습니다. (book_id={req.book_id})"
                    )

                pairs.append((book, req.quantity))

        # 상품 목록이 요청에 없으면 회원 장바구니의 선택 상품으로 주문한다.
        else:
            if member is None:
                raise BusinessError("주문 상품 정보가 필요합니다.")

            # 이 함수 안에서만 Cart 모델을 사용하므로 여기서 가져온다.
            from team_backend.app.models.cart import Cart

            cart = self.db.scalar(
                select(Cart).where(Cart.member_id == member.member_id)
            )

            if cart is None:
                raise BusinessError("장바구니가 비어 있습니다.")

            # 장바구니에서 사용자가 선택한 항목만 가져온다.
            rows = list(
                self.db.scalars(
                    select(CartItem).where(
                        CartItem.cart_id == cart.cart_id,
                        CartItem.is_selected == True,  # noqa: E712
                    )
                ).unique()
            )

            if not rows:
                raise BusinessError("선택된 장바구니 상품이 없습니다.")

            # 장바구니 항목마다 실제 도서 정보를 찾아 주문 목록에 추가한다.
            for item in rows:
                book = self.db.get(Book, item.book_id)

                # 장바구니에 있던 도서가 삭제된 경우 주문 목록에서 건너뛴다.
                if book is None:
                    continue

                pairs.append((book, item.quantity))

        # 어떤 방식으로도 주문 상품을 찾지 못했다면 오류를 발생시킨다.
        if not pairs:
            raise BusinessError("주문할 상품이 없습니다.")

        return pairs

    def create_order(
        self,
        member: Optional[Member],
        payload: OrderCreateRequest,
    ) -> Order:
        """주문을 만들고 재고, 쿠폰, 포인트, 결제 정보를 처리한다."""

        # 요청 상품 또는 장바구니에서 주문 대상 도서와 수량을 가져온다.
        pairs = self._resolve_items(member, payload)

        item_amount = 0.0  # 판매가 기준 상품 금액 합계
        list_amount = 0.0  # 정가 기준 상품 금액 합계

        # 상품 판매 가능 여부와 재고를 확인하고 상품 금액을 계산한다.
        for book, qty in pairs:
            if book.status in (BookStatus.DELETED, BookStatus.STOP):
                raise BusinessError(f"판매하지 않는 도서입니다: {book.title}")

            # 예약 판매 도서는 현재 재고가 부족해도 주문할 수 있다.
            if book.status != BookStatus.PREORDER and book.stock_qty < qty:
                raise BusinessError(
                    f"재고가 부족합니다: {book.title} (재고 {book.stock_qty}권)",
                    code="OUT_OF_STOCK",
                )

            item_amount += float(book.sale_price) * qty
            list_amount += float(book.list_price) * qty

        # ---- 쿠폰 할인 계산
        coupon_amount = 0.0
        member_coupon: Optional[MemberCoupon] = None
        free_ship_by_coupon = False

        if payload.member_coupon_id:
            # 비회원은 회원 쿠폰을 사용할 수 없다.
            if member is None:
                raise BusinessError("쿠폰은 회원만 사용할 수 있습니다.")

            # 요청한 쿠폰이 이 회원에게 발급된 쿠폰인지 확인한다.
            member_coupon = self.db.scalar(
                select(MemberCoupon).where(
                    MemberCoupon.member_coupon_id == payload.member_coupon_id,
                    MemberCoupon.member_id == member.member_id,
                )
            )

            if member_coupon is None:
                raise NotFoundError("쿠폰을 찾을 수 없습니다.")

            if member_coupon.is_used:
                raise BusinessError("이미 사용한 쿠폰입니다.")

            if member_coupon.expires_at < datetime.now(timezone.utc):
                raise BusinessError("유효기간이 지난 쿠폰입니다.")

            coupon = member_coupon.coupon

            # 무료 배송 쿠폰이면 할인액 대신 배송비 면제 여부를 기록한다.
            if coupon.coupon_type.value == "FREESHIP":
                free_ship_by_coupon = True
            else:
                # 일반 할인 쿠폰은 상품 금액을 기준으로 할인액을 계산한다.
                coupon_amount = coupon.calc_discount(item_amount)

                # 최소 주문 금액 등을 충족하지 못하면 계산된 할인액이 0 이하일 수 있다.
                if coupon_amount <= 0:
                    raise BusinessError(
                        f"최소 주문 금액 "
                        f"{int(coupon.min_order_amount):,}원 이상일 때 사용할 수 있습니다."
                    )

        # ---- 포인트 사용 가능 여부 확인
        point_used = float(payload.point_used or 0)

        if point_used:
            if member is None:
                raise BusinessError("포인트는 회원만 사용할 수 있습니다.")

            if point_used > member.point_balance:
                raise BusinessError("보유 포인트를 초과했습니다.")

            # 쿠폰 할인을 적용한 상품 금액보다 많은 포인트는 사용할 수 없다.
            if point_used > item_amount - coupon_amount:
                raise BusinessError("결제 금액을 초과하여 포인트를 사용할 수 없습니다.")

        # ---- 배송비 계산
        # 회원 등급별 무료 배송 기준이 있으면 그 기준을 사용한다.
        # 비회원이거나 등급 정보가 없으면 서비스 기본 설정을 사용한다.
        free_limit = (
            float(member.grade.free_ship_limit)
            if member is not None and member.grade is not None
            else float(settings.FREE_SHIP_LIMIT)
        )

        # 무료 배송 쿠폰을 썼거나 무료 배송 기준 금액을 넘으면 배송비는 0원이다.
        ship_fee = (
            0.0
            if (free_ship_by_coupon or item_amount >= free_limit)
            else float(settings.DEFAULT_SHIP_FEE)
        )

        # 최종 결제 금액 = 상품 금액 - 쿠폰 할인 - 사용 포인트 + 배송비
        total_amount = item_amount - coupon_amount - point_used + ship_fee

        # 계산 결과가 음수가 되지 않도록 0원으로 보정한다.
        if total_amount < 0:
            total_amount = 0.0

        # 회원 등급별 적립률이 있으면 적용하고, 없으면 기본 적립률을 사용한다.
        point_rate = (
            float(member.grade.point_rate) / 100.0
            if member is not None and member.grade is not None
            else settings.POINT_SAVE_RATE
        )

        # 적립 예정 포인트는 상품 금액에서 쿠폰 할인액을 뺀 금액을 기준으로 한다.
        point_saved = int((item_amount - coupon_amount) * point_rate)

        # 날짜와 일련번호를 조합한 주문 번호를 만든다.
        order_no = self._generate_order_no()

        # 주문의 기본 정보를 DB 객체로 만든다.
        order = Order(
            order_no=order_no,
            member_id=member.member_id if member else None,
            orderer_name=payload.orderer_name,
            orderer_phone=payload.orderer_phone,
            orderer_email=payload.orderer_email,
            status=OrderStatus.PENDING,
            item_amount=item_amount,
            discount_amount=max(list_amount - item_amount, 0),
            coupon_amount=coupon_amount,
            point_used=point_used,
            ship_fee=ship_fee,
            total_amount=total_amount,
            point_saved=point_saved,
            receiver=payload.receiver,
            receiver_phone=payload.receiver_phone,
            zipcode=payload.zipcode,
            address1=payload.address1,
            address2=payload.address2,
            request_memo=payload.request_memo,
            is_gift_wrap=payload.is_gift_wrap,
        )
        self.db.add(order)

        # flush는 INSERT를 DB에 보내 주문 번호(order_id)를 확보하지만,
        # 아직 트랜잭션을 최종 저장(commit)하지는 않는다.
        self.db.flush()

        # 주문 상품을 저장하고 재고를 차감한다.
        for book, qty in pairs:
            unit = float(book.sale_price)

            self.db.add(
                OrderItem(
                    order_id=order.order_id,
                    book_id=book.book_id,
                    book_title=book.title,
                    unit_price=unit,
                    quantity=qty,
                    item_discount=(float(book.list_price) - unit) * qty,
                    item_total=unit * qty,
                    status=OrderStatus.PENDING,
                )
            )

            # 주문한 수량만큼 재고를 줄이고 판매량을 늘린다.
            book.stock_qty -= qty
            book.sales_count = (book.sales_count or 0) + qty

            # 일반 판매 도서의 재고가 0 이하가 되면 품절 상태로 바꾼다.
            if book.stock_qty <= 0 and book.status == BookStatus.SALE:
                book.status = BookStatus.SOLDOUT

            # 재고가 언제, 얼마나 바뀌었는지 이력으로 남긴다.
            self.db.add(
                StockHistory(
                    book_id=book.book_id,
                    change_qty=-qty,
                    after_qty=book.stock_qty,
                    reason="ORDER",
                    ref_id=order.order_id,
                )
            )

        # 사용한 포인트를 회원 보유 포인트에서 차감하고 이력을 남긴다.
        if point_used and member is not None:
            member.point_balance -= int(point_used)

            self.db.add(
                PointHistory(
                    member_id=member.member_id,
                    reason=PointReason.ORDER_USE,
                    amount=-int(point_used),
                    balance_after=member.point_balance,
                    ref_id=order.order_id,
                    memo=f"주문 사용 ({order.order_no})",
                )
            )

        # 주문에 사용한 쿠폰을 사용 완료 상태로 바꾼다.
        if member_coupon is not None:
            member_coupon.is_used = True
            member_coupon.used_at = datetime.now(timezone.utc)
            member_coupon.order_id = order.order_id

        # 실제 PG 결제 요청 전 단계의 결제 정보를 준비한다.
        payment = Payment(
            order_id=order.order_id,
            pg_provider=settings.PG_PROVIDER,
            method=PaymentMethod(payload.payment_method),
            status=PaymentStatus.READY,
            amount=total_amount,
        )
        self.db.add(payment)

        # 배송 정보도 함께 만들어 둔다.
        self.db.add(
            Shipment(
                order_id=order.order_id,
                status=ShipmentStatus.READY,
                ship_fee=ship_fee,
            )
        )

        # 장바구니에서 주문한 경우, 주문에 사용한 선택 항목을 장바구니에서 지운다.
        if member is not None and not payload.items:
            from team_backend.app.models.cart import Cart

            cart = self.db.scalar(
                select(Cart).where(Cart.member_id == member.member_id)
            )

            if cart:
                self.db.query(CartItem).filter(
                    CartItem.cart_id == cart.cart_id,
                    CartItem.is_selected == True,  # noqa: E712
                ).delete(synchronize_session=False)

        # 주문, 상품, 재고, 포인트, 쿠폰, 결제 정보를 한 번에 저장한다.
        self.db.commit()
        self.db.refresh(order)

        logger.info(
            "주문 생성: order_no=%s amount=%s",
            order.order_no,
            total_amount,
        )
        return order

    def _generate_order_no(self) -> str:
        """날짜와 DB 일련번호를 조합해 주문 번호를 만든다."""

        # DB 시퀀스에서 다음 번호를 가져온다.
        seq = self.db.scalar(text("SELECT nextval('shop.orders_order_id_seq')"))

        # YYYYMMDD 형식의 날짜 뒤에 8자리 일련번호를 붙인다.
        return f"{datetime.now().strftime('%Y%m%d')}{int(seq):08d}"

    # ------------------------------------------------------------------ 주문 조회
    def _query_with_relations(self):
        """주문과 함께 응답에 필요한 연결 데이터를 조회하도록 설정한다."""

        return select(Order).options(
            # 주문 상품과 각 상품의 도서 정보를 함께 불러온다.
            selectinload(Order.items).selectinload(OrderItem.book),
            # 결제 정보도 함께 불러온다.
            selectinload(Order.payments),
            # 배송 정보와 배송 추적 기록을 함께 불러온다.
            selectinload(Order.shipments).selectinload(Shipment.tracking),
        )

    def get_order(
        self,
        order_id: int,
        member: Optional[Member] = None,
    ) -> Order:
        """주문 번호로 조회한다. 회원이 전달되면 본인 주문인지 확인한다."""

        order = self.db.scalar(
            self._query_with_relations().where(Order.order_id == order_id)
        )

        if order is None:
            raise NotFoundError("주문을 찾을 수 없습니다.")

        # 일반 회원은 자신의 주문만 볼 수 있다.
        # 관리자는 다른 회원의 주문도 조회할 수 있다.
        if (
            member is not None
            and not member.is_admin
            and order.member_id != member.member_id
        ):
            raise BusinessError(
                "본인의 주문만 조회할 수 있습니다.",
                status_code=403,
            )

        return order

    def get_by_order_no(
        self,
        order_no: str,
        email: Optional[str] = None,
    ) -> Order:
        """주문 번호로 조회한다. 이메일이 전달되면 주문자 이메일도 확인한다."""

        query = self._query_with_relations().where(Order.order_no == order_no)
        if email is not None:
            # 회원 주문은 로그인한 회원 전용이며 이메일은 대소문자를 구분하지 않는다.
            query = query.where(Order.member_id.is_(None), func.lower(Order.orderer_email) == email.lower())
        order = self.db.scalar(query)
        if order is None:
            raise NotFoundError("일치하는 비회원 주문을 찾을 수 없습니다.")

        return order

    def list_orders(
        self,
        member: Member,
        page: int = 1,
        size: int = 10,
        status: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Tuple[List[Order], int]:
        """회원의 주문 내역을 조건과 페이지에 맞춰 조회한다."""

        # 기본 조건은 현재 회원의 주문만 조회하는 것이다.
        conditions = [Order.member_id == member.member_id]

        # 상태나 날짜 조건이 전달된 경우 조회 조건에 추가한다.
        if status:
            conditions.append(Order.status == OrderStatus(status))
        if date_from:
            conditions.append(Order.ordered_at >= date_from)
        if date_to:
            conditions.append(Order.ordered_at <= date_to)

        # 조건에 맞는 전체 주문 수를 구해 페이지 정보에 사용한다.
        total = (
            self.db.scalar(
                select(func.count()).select_from(Order).where(*conditions)
            )
            or 0
        )

        # 최신 주문부터 정렬하고, 요청한 페이지에 해당하는 데이터만 가져온다.
        rows = list(
            self.db.scalars(
                self._query_with_relations()
                .where(*conditions)
                .order_by(Order.ordered_at.desc())
                .offset((page - 1) * size)
                .limit(size)
            ).unique()
        )

        return rows, total

    def list_all_orders(
        self,
        page: int = 1,
        size: int = 20,
        status: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> Tuple[List[Order], int]:
        """관리자가 전체 주문을 조회한다."""

        conditions = []

        # 상태가 지정되면 해당 상태의 주문만 조회한다.
        if status:
            conditions.append(Order.status == OrderStatus(status))

        # 검색어가 있으면 주문 번호, 주문자, 수령인 정보에서 찾는다.
        if keyword:
            kw = f"%{keyword}%"
            from sqlalchemy import or_

            conditions.append(
                or_(
                    Order.order_no.ilike(kw),
                    Order.orderer_name.ilike(kw),
                    Order.orderer_email.ilike(kw),
                    Order.receiver.ilike(kw),
                )
            )

        # 검색 조건에 맞는 전체 주문 수를 계산한다.
        total = (
            self.db.scalar(
                select(func.count()).select_from(Order).where(*conditions)
            )
            or 0
        )

        # 최신 주문부터 정렬하고 페이지 크기만큼 가져온다.
        rows = list(
            self.db.scalars(
                self._query_with_relations()
                .where(*conditions)
                .order_by(Order.ordered_at.desc())
                .offset((page - 1) * size)
                .limit(size)
            ).unique()
        )

        return rows, total

    # ------------------------------------------------------------ 주문 상태 변경
    def change_status(
        self,
        order_id: int,
        new_status: str,
        memo: Optional[str] = None,
    ) -> Order:
        """허용된 규칙에 따라 주문 상태를 변경하고 필요한 후속 처리를 한다."""

        order = self.get_order(order_id)
        target = OrderStatus(new_status)

        # 현재 상태에서 이동 가능한 상태 목록을 가져온다.
        allowed = ALLOWED_TRANSITIONS.get(order.status, set())

        # 허용 목록에 없는 상태 변경은 막는다.
        if target not in allowed:
            raise BusinessError(
                f"'{STATUS_LABELS[order.status]}' 상태에서 "
                f"'{STATUS_LABELS[target]}' 로 변경할 수 없습니다.",
                code="INVALID_TRANSITION",
            )

        now = datetime.now(timezone.utc)
        order.status = target

        # 주문에 포함된 상품 상태도 주문 상태와 맞춘다.
        for item in order.items:
            item.status = target

        shipment = order.shipments[0] if order.shipments else None

        # 결제가 완료되면 결제 완료 시간을 기록한다.
        if target == OrderStatus.PAID:
            order.paid_at = now

        # 배송이 시작되면 배송 상태, 시작 시간, 추적 기록을 추가한다.
        elif target == OrderStatus.SHIPPING and shipment:
            shipment.status = ShipmentStatus.IN_TRANSIT
            shipment.shipped_at = now
            self.db.add(
                ShipmentTracking(
                    shipment_id=shipment.shipment_id,
                    status=ShipmentStatus.IN_TRANSIT,
                    location="허브 터미널",
                    description="상품이 배송을 시작했습니다.",
                )
            )

        # 배송 완료 시 주문과 배송 정보를 갱신하고 추적 기록을 남긴다.
        elif target == OrderStatus.DELIVERED:
            order.delivered_at = now

            if shipment:
                shipment.status = ShipmentStatus.DELIVERED
                shipment.delivered_at = now
                self.db.add(
                    ShipmentTracking(
                        shipment_id=shipment.shipment_id,
                        status=ShipmentStatus.DELIVERED,
                        location="배송지",
                        description="배송이 완료되었습니다.",
                    )
                )

        # 구매 확정 시 적립 포인트를 회원에게 지급한다.
        elif target == OrderStatus.CONFIRMED:
            order.confirmed_at = now
            self._save_point(order)

        self.db.commit()
        self.db.refresh(order)

        logger.info(
            "주문 상태 변경: %s -> %s (%s)",
            order.order_no,
            target.value,
            memo or "",
        )
        return order

    def _save_point(self, order: Order) -> None:
        """구매 확정 시 회원에게 포인트를 적립한다."""

        # 비회원 주문이거나 적립할 포인트가 없으면 종료한다.
        if not order.member_id or not order.point_saved:
            return

        member = self.db.get(Member, order.member_id)
        if member is None:
            return

        amount = int(order.point_saved)

        # 회원 잔액과 주문 횟수를 갱신한다.
        member.point_balance += amount
        member.order_count = (member.order_count or 0) + 1

        # 적립 내역을 기록하고, 적립 포인트의 만료일은 1년 뒤로 설정한다.
        self.db.add(
            PointHistory(
                member_id=member.member_id,
                reason=PointReason.ORDER_SAVE,
                amount=amount,
                balance_after=member.point_balance,
                ref_id=order.order_id,
                memo=f"구매 확정 적립 ({order.order_no})",
                expires_at=datetime.now(timezone.utc) + timedelta(days=365),
            )
        )

        # 회원의 주문 실적에 따라 등급을 다시 계산한다.
        self.db.execute(
            text("SELECT shop.fn_refresh_member_grade(:mid)"),
            {"mid": member.member_id},
        )

    def confirm_purchase(self, order_id: int, member: Member) -> Order:
        """회원이 배송 완료된 주문을 직접 구매 확정한다."""

        # 회원 본인의 주문인지 먼저 확인한다.
        order = self.get_order(order_id, member)

        # 배송 완료 상태가 아니면 구매 확정할 수 없다.
        if order.status != OrderStatus.DELIVERED:
            raise BusinessError("배송 완료 상태에서만 구매 확정이 가능합니다.")

        # 공통 상태 변경 메서드에서 상태와 포인트를 처리한다.
        return self.change_status(
            order_id,
            OrderStatus.CONFIRMED.value,
            "회원 구매 확정",
        )

    def auto_confirm_delivered(self) -> int:
        """배송 완료 후 설정된 기간이 지난 주문을 자동으로 구매 확정한다."""

        # 자동 구매 확정 기준 날짜를 계산한다.
        deadline = datetime.now(timezone.utc) - timedelta(
            days=settings.ORDER_CONFIRM_DAYS
        )

        # 기준 날짜보다 오래전에 배송 완료된 주문을 찾는다.
        targets = list(
            self.db.scalars(
                select(Order).where(
                    Order.status == OrderStatus.DELIVERED,
                    Order.delivered_at <= deadline,
                )
            )
        )

        # 찾은 주문을 하나씩 구매 확정 상태로 바꾼다.
        for order in targets:
            try:
                self.change_status(
                    order.order_id,
                    OrderStatus.CONFIRMED.value,
                    "자동 구매 확정",
                )
            except BusinessError:  # pragma: no cover
                # 상태 변경이 불가능한 주문은 건너뛰고 다음 주문을 처리한다.
                continue

        return len(targets)

    # ------------------------------------------------------------ 주문 취소 / 환불
    def cancel_order(
        self,
        order_id: int,
        member: Optional[Member],
        reason_code: str,
        reason_text: Optional[str] = None,
    ) -> Order:
        """주문을 취소하고 재고, 포인트, 쿠폰, 결제 정보를 정리한다."""

        # 주문을 찾고, 회원 요청이라면 본인 주문인지 확인한다.
        order = self.get_order(order_id, member)

        # 취소할 수 없는 상태의 주문은 취소를 막는다.
        if not order.is_cancelable:
            raise BusinessError(
                f"현재 상태({STATUS_LABELS[order.status]})에서는 취소할 수 없습니다.",
                code="NOT_CANCELABLE",
            )

        now = datetime.now(timezone.utc)

        # ---- 재고 복원
        for item in order.items:
            book = self.db.get(Book, item.book_id)

            if book:
                # 주문 때 차감했던 재고를 되돌리고 판매량도 낮춘다.
                book.stock_qty += item.quantity
                book.sales_count = max(
                    (book.sales_count or 0) - item.quantity,
                    0,
                )

                # 품절 도서의 재고가 다시 생기면 판매 상태로 바꾼다.
                if book.status == BookStatus.SOLDOUT and book.stock_qty > 0:
                    book.status = BookStatus.SALE

                # 재고 복원 내역을 기록한다.
                self.db.add(
                    StockHistory(
                        book_id=book.book_id,
                        change_qty=item.quantity,
                        after_qty=book.stock_qty,
                        reason="CANCEL",
                        ref_id=order.order_id,
                    )
                )

            # 주문 상품 상태도 취소로 바꾼다.
            item.status = OrderStatus.CANCELLED

        # ---- 사용 포인트 복원
        if order.member_id and order.point_used:
            m = self.db.get(Member, order.member_id)

            if m:
                restore = int(order.point_used)
                m.point_balance += restore

                # 복원된 포인트 내역을 기록한다.
                self.db.add(
                    PointHistory(
                        member_id=m.member_id,
                        reason=PointReason.CANCEL_RESTORE,
                        amount=restore,
                        balance_after=m.point_balance,
                        ref_id=order.order_id,
                        memo=f"주문 취소 복원 ({order.order_no})",
                    )
                )

        # ---- 사용 쿠폰 복원
        used_coupon = self.db.scalar(
            select(MemberCoupon).where(MemberCoupon.order_id == order.order_id)
        )

        if used_coupon:
            # 쿠폰을 다시 사용할 수 있도록 미사용 상태로 돌린다.
            used_coupon.is_used = False
            used_coupon.used_at = None
            used_coupon.order_id = None

        # ---- 결제 취소 및 환불 기록
        payment = order.main_payment

        if payment and payment.status == PaymentStatus.PAID:
            # 결제가 끝난 주문이면 결제 상태와 취소 금액을 기록한다.
            payment.status = PaymentStatus.CANCELLED
            payment.cancelled_amount = payment.amount
            payment.cancelled_at = now

            # 실제 환불 처리 내용을 DB에 기록한다.
            self.db.add(
                Refund(
                    order_id=order.order_id,
                    payment_id=payment.payment_id,
                    refund_amount=payment.amount,
                    point_restore=order.point_used,
                    reason_code=reason_code,
                    reason_text=reason_text,
                    completed_at=now,
                )
            )

        elif payment:
            # 결제가 완료되기 전 취소된 경우 결제 상태만 취소로 바꾼다.
            payment.status = PaymentStatus.CANCELLED
            payment.cancelled_at = now

        # 배송이 준비되었거나 진행 중이면 배송 상태를 실패로 표시한다.
        if order.shipments:
            order.shipments[0].status = ShipmentStatus.FAILED

        # 주문 상태와 취소 시각을 기록한다.
        order.status = OrderStatus.CANCELLED
        order.cancelled_at = now

        self.db.commit()
        self.db.refresh(order)

        logger.info("주문 취소: %s reason=%s", order.order_no, reason_code)
        return order

    def request_return(
        self,
        order_id: int,
        member: Member,
        reason_text: Optional[str],
    ) -> Order:
        """회원의 반품 요청을 확인하고 반품 접수 상태로 바꾼다."""

        # 회원 본인의 주문인지 확인한다.
        order = self.get_order(order_id, member)

        # 배송 중이거나 배송 완료된 주문만 반품 요청할 수 있다.
        if order.status not in (
            OrderStatus.SHIPPING,
            OrderStatus.DELIVERED,
        ):
            raise BusinessError(
                "배송 중 또는 배송 완료 상태에서만 반품 접수가 가능합니다."
            )

        # 배송 완료 후 7일이 지났으면 반품 요청을 막는다.
        if order.delivered_at and (
            datetime.now(timezone.utc) - order.delivered_at
        ) > timedelta(days=7):
            raise BusinessError("배송 완료 후 7일이 지나 반품 접수가 불가합니다.")

        # 상태 변경 규칙을 확인하면서 반품 접수 상태로 바꾼다.
        return self.change_status(
            order_id,
            OrderStatus.RETURN_REQ.value,
            reason_text,
        )

    # ------------------------------------------------------------------ 주문 통계
    def member_order_stats(self, member_id: int) -> dict:
        """마이페이지에 표시할 회원 주문 통계를 조회한다."""

        # 주문 수와 상태별 건수, 결제 완료 금액을 DB에서 한 번에 계산한다.
        sql = text(
            """
            SELECT
              COUNT(*)                                                       AS total,
              COUNT(*) FILTER (WHERE status IN ('PAID','PREPARING'))         AS preparing,
              COUNT(*) FILTER (WHERE status = 'SHIPPING')                    AS shipping,
              COUNT(*) FILTER (WHERE status IN ('DELIVERED','CONFIRMED'))    AS delivered,
              COUNT(*) FILTER (WHERE status = 'CANCELLED')                   AS cancelled,
              COALESCE(SUM(total_amount) FILTER (
                  WHERE status IN ('PAID','PREPARING','SHIPPING','DELIVERED','CONFIRMED')), 0) AS paid_amount
              FROM shop.orders WHERE member_id = :mid
            """
        )

        # :mid 자리에 회원 번호를 넣어 SQL을 실행하고 결과를 딕셔너리로 바꾼다.
        row = self.db.execute(
            sql,
            {"mid": member_id},
        ).mappings().first()

        return dict(row) if row else {}