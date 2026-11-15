"""
주문 상태 전환 서비스 (책 6.4절 상태 머신)
허용된 상태 전환만 수행하고, 변경 이력 저장과 재고 복구를 함께 처리합니다.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.api_errors import api_error
from app.models.order_model import Order, OrderStatus, OrderStatusHistory
from app.models.product_model import Product

logger = logging.getLogger(__name__)


# ── 허용된 상태 전환 규칙
ALLOWED_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.PENDING:      {OrderStatus.PAYMENT_WAIT, OrderStatus.CANCELLED},
    OrderStatus.PAYMENT_WAIT: {OrderStatus.PAID,         OrderStatus.CANCELLED},
    OrderStatus.PAID:         {OrderStatus.PREPARING,    OrderStatus.REFUNDED},
    OrderStatus.PREPARING:    {OrderStatus.SHIPPED,      OrderStatus.REFUNDED},
    OrderStatus.SHIPPED:      {OrderStatus.DELIVERED},
    OrderStatus.DELIVERED:    {OrderStatus.REFUNDED},
    OrderStatus.CANCELLED:    set(),  # 최종 상태
    OrderStatus.REFUNDED:     set(),  # 최종 상태
}

# ── 취소 가능한 상태 목록
CANCELLABLE_STATUSES = {
    OrderStatus.PENDING,
    OrderStatus.PAYMENT_WAIT,
    OrderStatus.PAID,
}


class OrderService:
    def __init__(self, db: Session):
        self.db = db

    # 현재 상태에서 새 상태로 바꿀 수 있는지 확인하고, 안 되면 409 오류를 발생시킵니다.
    def ensure_transition_allowed(self, order: Order, new_status: OrderStatus) -> None:
        current_status = OrderStatus(order.status)
        allowed = ALLOWED_TRANSITIONS.get(current_status, set())
        if new_status not in allowed:
            raise api_error(
                409, "INVALID_ORDER_STATUS",
                f"주문 상태를 [{current_status.value}]에서 [{new_status.value}]으로 변경할 수 없습니다. "
                f"허용된 전환: {sorted(s.value for s in allowed)}",
            )

    def transition_order_status(
        self,
        order: Order,
        new_status: OrderStatus,
        changed_by: int | None,
        reason: str | None = None,
    ) -> Order:
        """
        주문 상태를 전환합니다.
        허용되지 않은 전환은 409 Conflict 오류를 발생시킵니다.
        """
        self.ensure_transition_allowed(order, new_status)

        try:
            old_status = OrderStatus(order.status)
            order.status = new_status.value
            # 기존 응답 필드(payment_status)도 같은 값으로 맞춥니다.
            order.payment_status = new_status.value

            # ── 상태별 부수 처리
            if new_status == OrderStatus.PAID:
                order.paid_at = datetime.now(timezone.utc)
            elif new_status in (OrderStatus.CANCELLED, OrderStatus.REFUNDED):
                self._restore_stock(order)  # 재고 복구

            # ── 이력 저장
            self.db.add(OrderStatusHistory(
                order_id=order.id,
                from_status=old_status.value,
                to_status=new_status.value,
                changed_by=changed_by,
                reason=reason,
            ))
            self.db.commit()
            self.db.refresh(order)

            logger.info(
                "주문 상태 변경: %s %s → %s (by member=%s)",
                order.order_number, old_status.value, new_status.value, changed_by,
            )
            return order

        except Exception:
            self.db.rollback()
            logger.error("상태 전환 오류: 주문 %s", order.order_number, exc_info=True)
            raise

    def _restore_stock(self, order: Order) -> None:
        """주문 취소/환불 시 재고를 복구합니다."""
        quantities = {line["product_id"]: line["quantity"] for line in order.items}
        # 주문 생성 때와 같은 ID 순서로 상품을 잠가 동시 주문과 충돌하지 않게 합니다.
        products = self.db.scalars(
            select(Product).where(Product.id.in_(quantities)).order_by(Product.id).with_for_update())
        for product in products:
            product.stock += quantities[product.id]
            logger.info(
                "재고 복구: 상품 %s (%s) +%s개 (주문 %s)",
                product.id, product.title, quantities[product.id], order.order_number,
            )
