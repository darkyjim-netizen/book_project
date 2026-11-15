"""주문 결제 정보를 처리하는 서비스."""
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import BusinessError, NotFoundError, PaymentError
from app.models.enums import OrderStatus, PaymentMethod, PaymentStatus
from app.models.order import Order, Payment, PaymentLog
from app.schemas.order import PaymentConfirmRequest
from app.services.payment_gateway import PgGateway, get_gateway

logger = logging.getLogger(__name__)


class PaymentService:
    """결제 승인·취소와 결제 정보 저장을 담당한다."""

    def __init__(
        self,
        db: Session,
        gateway: Optional[PgGateway] = None,
    ):
        self.db = db

        # 테스트용 게이트웨이를 전달하면 그것을 쓰고,
        # 전달하지 않으면 설정에 따라 모의 PG 또는 토스 게이트웨이를 선택한다.
        self.gateway = gateway or get_gateway()

    def _log(
        self,
        payment: Optional[Payment],
        order_no: str,
        action: str,
        req: Dict,
        res: Dict,
    ) -> None:
        """PG 요청과 응답을 결제 로그 테이블에 기록한다."""

        self.db.add(
            PaymentLog(
                payment_id=payment.payment_id if payment else None,
                order_no=order_no,
                action=action,
                request_body=req,
                response_body=res,
                result_code=str(res.get("result_code")),
            )
        )

    def get_payment(self, order_id: int) -> Payment:
        """주문에 연결된 결제 정보를 조회한다."""

        # 같은 주문에 결제 정보가 여러 개라면 가장 최근 정보를 가져온다.
        payment = self.db.scalar(
            select(Payment)
            .where(Payment.order_id == order_id)
            .order_by(Payment.payment_id.desc())
        )

        if payment is None:
            raise NotFoundError("결제 정보를 찾을 수 없습니다.")

        return payment

    # ------------------------------------------------------------------ 결제 승인
    def request_payment(
        self,
        order_id: int,
        extra: Optional[Dict] = None,
    ) -> Payment:
        """
        PG에 결제 승인을 요청하고 결과를 DB에 반영한다.

        토스 결제라면 extra에 payment_key가 있어야 한다.
        예: {"payment_key": "토스에서_받은_결제키"}
        """

        # 주문이 실제로 존재하는지 확인한다.
        order = self.db.get(Order, order_id)
        if order is None:
            raise NotFoundError("주문을 찾을 수 없습니다.")

        # 결제 대기 상태인 주문만 승인 요청할 수 있다.
        if order.status != OrderStatus.PENDING:
            raise BusinessError("결제 대기 상태의 주문만 결제할 수 있습니다.")

        payment = self.get_payment(order_id)

        # 이미 결제된 주문의 중복 승인을 막는다.
        if payment.status == PaymentStatus.PAID:
            raise BusinessError("이미 결제가 완료된 주문입니다.")

        extra = extra or {}

        # payment_key는 토스에서 프론트엔드 결제창으로 받은 값이다.
        # 로그에는 결제 키를 남기지 않도록 별도로 제외한다.
        log_request = {
            key: value
            for key, value in extra.items()
            if key != "payment_key"
        }

        try:
            # 실제 PG 호출은 gateway가 담당한다.
            result = self.gateway.approve(order, payment, extra)

        except Exception as exc:
            # PG 연결 오류 등 예외가 발생하면 결제 실패로 기록한다.
            payment.status = PaymentStatus.FAILED
            self._log(
                payment,
                order.order_no,
                "APPROVE",
                log_request,
                {"error": str(exc)},
            )
            self.db.commit()

            raise PaymentError(
                f"결제 승인 중 오류가 발생했습니다: {exc}"
            ) from exc

        # 성공과 실패 모두 PG 응답을 로그로 기록한다.
        self._log(
            payment,
            order.order_no,
            "APPROVE",
            log_request,
            result,
        )

        # 게이트웨이 공통 응답에서 성공 코드가 아니면 실패 처리한다.
        if str(result.get("result_code")) != "0000":
            payment.status = PaymentStatus.FAILED
            self.db.commit()

            raise PaymentError(
                result.get("result_msg") or "결제가 거절되었습니다."
            )

        # 응답에 결제 거래 키가 있으면 저장한다.
        # 토스의 paymentKey는 기존 모델의 pg_tid 필드에 보관한다.
        payment.pg_tid = result.get("tid")

        now = datetime.now(timezone.utc)

        if payment.method == PaymentMethod.VBANK:
            # 가상계좌는 계좌 발급 직후 결제 완료가 아니라 입금 대기 상태다.
            payment.status = PaymentStatus.READY
            payment.vbank_bank = result.get("vbank_bank")
            payment.vbank_no = result.get("vbank_no")
            payment.vbank_holder = result.get("vbank_holder")

            # PG가 입금 기한을 주면 그 값을 사용하고,
            # 주지 않으면 기본적으로 3일 뒤를 기한으로 설정한다.
            due = result.get("vbank_due")
            payment.vbank_due = (
                datetime.fromisoformat(due)
                if isinstance(due, str)
                else now + timedelta(days=3)
            )

            # 입금 전이므로 주문과 주문 상품은 PENDING 상태를 유지한다.

        else:
            # 카드 등 즉시 승인되는 결제는 결제와 주문을 완료 상태로 바꾼다.
            payment.status = PaymentStatus.PAID
            payment.approved_at = now
            payment.card_name = result.get("card_name")
            payment.card_no_masked = result.get("card_no_masked")
            payment.receipt_url = result.get("receipt_url")

            order.status = OrderStatus.PAID
            order.paid_at = now

            # 주문 안의 상품 상태도 주문 상태와 맞춘다.
            for item in order.items:
                item.status = OrderStatus.PAID

        self.db.commit()
        self.db.refresh(payment)

        logger.info(
            "결제 처리 완료: %s %s",
            order.order_no,
            payment.status.value,
        )

        return payment

    # ------------------------------------------------------------------ PG 콜백
    def confirm_callback(
        self,
        payload: PaymentConfirmRequest,
    ) -> Payment:
        """
        기존 PG 콜백 형식으로 결제 결과를 확정한다.

        주의:
        이 메서드는 payload에 result_code, pg_tid 등이 들어오는 기존 콜백용이다.
        토스 웹훅 요청 형식과 다르므로 토스 웹훅에는 그대로 사용하지 않는다.
        """

        # PG가 전달한 주문 번호로 주문을 찾는다.
        order = self.db.scalar(
            select(Order).where(Order.order_no == payload.order_no)
        )

        if order is None:
            raise NotFoundError("주문을 찾을 수 없습니다.")

        payment = self.get_payment(order.order_id)

        # 콜백도 결제 처리 기록으로 저장한다.
        self._log(
            payment,
            order.order_no,
            "CALLBACK",
            payload.model_dump(),
            {"received": True},
        )

        # PG에서 실패 코드가 오면 결제 실패로 처리한다.
        if payload.result_code != "0000":
            payment.status = PaymentStatus.FAILED
            self.db.commit()
            raise PaymentError("결제가 실패 처리되었습니다.")

        # PG가 알려 준 금액과 서버에 저장된 결제 금액이 같은지 확인한다.
        if int(payload.amount) != int(payment.amount):
            logger.error(
                "결제 금액 불일치: order=%s expected=%s actual=%s",
                order.order_no,
                payment.amount,
                payload.amount,
            )
            raise PaymentError("결제 금액이 일치하지 않습니다.")

        now = datetime.now(timezone.utc)

        payment.pg_tid = payload.pg_tid
        payment.status = PaymentStatus.PAID
        payment.approved_at = now
        payment.card_name = payload.card_name or payment.card_name
        payment.card_no_masked = (
            payload.card_no_masked or payment.card_no_masked
        )

        # 아직 결제 대기 상태인 주문일 때만 주문 상태를 갱신한다.
        if order.status == OrderStatus.PENDING:
            order.status = OrderStatus.PAID
            order.paid_at = now

            for item in order.items:
                item.status = OrderStatus.PAID

        self.db.commit()
        self.db.refresh(payment)

        return payment

    # ------------------------------------------------------------------ 결제 취소
    def cancel_payment(
        self,
        order_id: int,
        amount: Optional[float],
        reason: str,
    ) -> Payment:
        """결제를 전체 또는 부분 취소한다."""

        payment = self.get_payment(order_id)

        # 결제가 완료됐거나 일부 취소된 결제만 추가 취소할 수 있다.
        if payment.status not in (
            PaymentStatus.PAID,
            PaymentStatus.PARTIAL_CANCELLED,
        ):
            raise BusinessError("결제 완료 상태에서만 취소할 수 있습니다.")

        # 아직 취소되지 않은 금액을 계산한다.
        remain = float(payment.amount) - float(payment.cancelled_amount)

        # 취소 금액이 생략되면 남은 전액을 취소한다.
        target = float(amount) if amount else remain

        # 0원 이하 또는 남은 금액을 초과하는 취소는 허용하지 않는다.
        if target <= 0 or target > remain:
            raise BusinessError(
                f"취소 가능 금액은 {int(remain):,}원입니다."
            )

        order = self.db.get(Order, order_id)

        # 실제 PG 취소 요청은 gateway가 담당한다.
        result = self.gateway.cancel(payment, target, reason)

        # 취소 요청과 PG 응답을 기록한다.
        self._log(
            payment,
            order.order_no if order else "",
            "CANCEL",
            {"amount": target, "reason": reason},
            result,
        )

        # PG가 실패를 반환하면 취소 금액이나 상태를 바꾸지 않는다.
        if str(result.get("result_code")) != "0000":
            self.db.commit()
            raise PaymentError(
                result.get("result_msg") or "결제 취소에 실패했습니다."
            )

        # 이번 취소 금액을 누적하고 취소 시각을 저장한다.
        payment.cancelled_amount = (
            float(payment.cancelled_amount) + target
        )
        payment.cancelled_at = datetime.now(timezone.utc)

        # 전액 취소했는지에 따라 결제 상태를 구분한다.
        payment.status = (
            PaymentStatus.CANCELLED
            if float(payment.cancelled_amount) >= float(payment.amount)
            else PaymentStatus.PARTIAL_CANCELLED
        )

        self.db.commit()
        self.db.refresh(payment)

        logger.info(
            "결제 취소: payment_id=%s amount=%s",
            payment.payment_id,
            target,
        )

        return payment

    # ------------------------------------------------------------------ 가상계좌 만료
    def expire_unpaid_vbank(self, hours: int = 72) -> int:
        """입금 기한이 지난 가상계좌 주문을 취소한다."""

        # 현재 시각에서 지정한 시간을 뺀 시각을 만료 기준으로 삼는다.
        deadline = datetime.now(timezone.utc) - timedelta(hours=hours)

        # 입금 대기 중이고 요청 시각이 기준보다 오래된 가상계좌를 찾는다.
        rows = list(
            self.db.scalars(
                select(Payment).where(
                    Payment.method == PaymentMethod.VBANK,
                    Payment.status == PaymentStatus.READY,
                    Payment.requested_at <= deadline,
                )
            )
        )

        # 주문 취소 서비스로 재고·쿠폰·포인트 등 주문 관련 처리를 맡긴다.
        from app.services.order_service import OrderService

        order_service = OrderService(self.db)
        count = 0

        for payment in rows:
            try:
                order_service.cancel_order(
                    payment.order_id,
                    None,
                    "VBANK_EXPIRED",
                    "입금 기한 초과",
                )
                count += 1

            except BusinessError:
                # 이미 취소됐거나 취소할 수 없는 주문은 건너뛴다.
                continue

        return count