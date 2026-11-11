
import base64
import logging
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.core import config
from app.core.api_errors import api_error
from app.crud.order_crud import get_order_by_number
from app.models.order_model import Order, OrderStatus
from app.services.order_status_service import OrderService

logger = logging.getLogger(__name__)


class TossPaymentService:
    """토스페이먼츠 결제 연동 서비스"""

    # PG사 응답이 늦을 때 무한 대기를 막는 제한 시간(초)입니다.
    TIMEOUT = 30.0

    def __init__(self, db: Session):
        self.db = db
        self.order_service = OrderService(db)
        self.base_url = f"{config.toss_api_base_url()}/v1"

    @staticmethod
    def _make_auth_header(secret_key: str) -> str:
        """토스페이먼츠 Basic Auth 헤더 생성: Base64(secretKey:)"""
        credentials = base64.b64encode(f"{secret_key}:".encode("utf-8")).decode("utf-8")
        return f"Basic {credentials}"

    def _headers(self) -> dict[str, str]:
        secret_key = config.toss_secret_key()
        if not secret_key:
            raise api_error(500, "PAYMENT_CONFIG_ERROR", "TOSS_SECRET_KEY가 설정되지 않았습니다.")
        return {
            "Authorization": self._make_auth_header(secret_key),
            "Content-Type": "application/json",
        }

    @staticmethod
    def _error_message(response: httpx.Response, default: str) -> str:
        """PG사 오류 응답에서 사용자에게 보여 줄 메시지를 꺼냅니다."""
        try:
            return response.json().get("message") or default
        except (ValueError, AttributeError):
            return default

    async def _post(self, path: str, body: dict[str, Any]) -> httpx.Response:
        """토스페이먼츠 API를 호출합니다. 응답 지연과 연결 오류를 API 오류로 바꿉니다."""
        try:
            async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
                return await client.post(f"{self.base_url}{path}", headers=self._headers(), json=body)
        except httpx.TimeoutException:
            logger.error("토스페이먼츠 응답 지연: %s", path)
            raise api_error(504, "PAYMENT_TIMEOUT",
                            "결제 서버 응답이 지연되고 있습니다. 결제 내역을 확인해주세요.") from None
        except httpx.RequestError as exc:
            logger.error("토스페이먼츠 연결 오류: %s | %s", path, exc)
            raise api_error(502, "PAYMENT_GATEWAY_ERROR", "결제 서버에 연결할 수 없습니다.") from None

    def get_payment_ready_data(self, order: Order) -> dict[str, Any]:
        """
        프론트엔드에서 토스 결제창을 초기화하는 데 필요한 데이터를 반환합니다.
        금액은 서버에서 계산한 값을 전달하여 위변조를 방지합니다.
        """
        return {
            "client_key": config.toss_client_key(),
            "order_id": order.order_number,        # PG사 주문 ID = 우리 주문번호
            "order_name": self._make_order_name(order),
            "amount": order.total,                 # 서버 계산 금액
            "customer_name": order.receiver_name,
            "success_url": config.payment_success_url(),
            "fail_url": config.payment_fail_url(),
        }

    @staticmethod
    def _make_order_name(order: Order) -> str:
        """주문 상품명 요약 (예: "파이썬 책 외 2종")"""
        if not order.items:
            return "상품"
        first = order.items[0]["title"]
        rest = len(order.items) - 1
        return first if rest == 0 else f"{first} 외 {rest}종"

    async def confirm_payment(self, payment_key: str, order_number: str, amount: int) -> dict[str, Any]:
        """
        PG사 서버에 최종 결제 승인을 요청합니다. (서버 사이드 핵심 보안 단계)

        1. DB에서 주문 조회
        2. 클라이언트 전달 금액과 DB 금액 일치 검증
        3. 주문 상태 → PAYMENT_WAIT
        4. 토스페이먼츠 승인 API 호출
        5. 주문 상태 → PAID + 결제키 저장
        """
        # 1. 주문 조회
        order = get_order_by_number(self.db, order_number)
        if order is None:
            raise api_error(404, "ORDER_NOT_FOUND", f"주문번호 {order_number}를 찾을 수 없습니다.")

        # 같은 결제의 성공 콜백이 다시 들어온 경우(새로고침 등)에는 이미 끝난 승인을 그대로 돌려줍니다.
        if order.status == OrderStatus.PAID and order.payment_key == payment_key:
            return {"success": True, "order": order, "payment_data": None}

        # 2. 금액 검증 (위변조 방지)
        if order.total != amount:
            logger.warning("[결제 금액 불일치] 주문: %s | DB: %s원 | 클라이언트: %s원",
                           order_number, order.total, amount)
            raise api_error(400, "PAYMENT_AMOUNT_MISMATCH", "결제 금액이 일치하지 않습니다. 결제가 취소됩니다.")

        # 3. 결제 중 상태로 전환
        self.order_service.transition_order_status(
            order=order, new_status=OrderStatus.PAYMENT_WAIT,
            changed_by=order.member_id, reason="결제 승인 요청",
        )

        # 4. 토스페이먼츠 승인 API 호출
        response = await self._post("/payments/confirm", {
            "paymentKey": payment_key,
            "orderId": order_number,
            "amount": amount,
        })

        if response.status_code == 200:
            payment_data = response.json()
            # 5. 주문 상태 → PAID + 결제키 저장
            order.payment_key = payment_key
            self.order_service.transition_order_status(
                order=order, new_status=OrderStatus.PAID,
                changed_by=order.member_id, reason="결제 승인 완료",
            )
            logger.info("결제 승인 완료: %s | %s원", order_number, amount)
            return {"success": True, "order": order, "payment_data": payment_data}

        message = self._error_message(response, "알 수 없는 오류")
        logger.error("결제 승인 실패: %s | %s", order_number, message)
        self.order_service.transition_order_status(
            order=order, new_status=OrderStatus.CANCELLED,
            changed_by=order.member_id, reason=f"PG사 결제 실패: {message}",
        )
        raise api_error(402, "PAYMENT_FAILED", f"결제 실패: {message}")

    async def cancel_payment(self, order: Order, cancel_reason: str) -> dict[str, Any]:
        """
        결제를 전액 취소합니다. (부분 취소는 지원하지 않습니다.)
        payment_key가 없으면 DB 상태만 CANCELLED로 변경합니다.
        """
        if not order.payment_key:
            # 결제 전 취소 (DB 상태만 변경)
            self.order_service.transition_order_status(
                order=order, new_status=OrderStatus.CANCELLED,
                changed_by=order.member_id, reason=cancel_reason,
            )
            return {"success": True, "message": "결제 전 취소 완료"}

        new_status = OrderStatus.REFUNDED if order.status == OrderStatus.PAID else OrderStatus.CANCELLED
        # 돈만 환불되고 주문 상태는 못 바꾸는 일이 없도록 PG사를 호출하기 전에 전환 가능 여부를 확인합니다.
        self.order_service.ensure_transition_allowed(order, new_status)

        # PG사 취소 API 호출 (cancelAmount를 보내지 않으면 전액 취소)
        response = await self._post(f"/payments/{order.payment_key}/cancel", {"cancelReason": cancel_reason})

        if response.status_code == 200:
            self.order_service.transition_order_status(
                order=order, new_status=new_status,
                changed_by=order.member_id, reason=cancel_reason,
            )
            return {"success": True, "cancel_data": response.json()}

        message = self._error_message(response, "오류")
        logger.error("결제 취소 실패: %s | %s", order.order_number, message)
        raise api_error(400, "PAYMENT_CANCEL_FAILED", f"결제 취소 실패: {message}")
