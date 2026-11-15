"""모의 PG와 토스페이먼츠 PG 게이트웨이."""
import logging
import random
import string
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Dict

import requests

from app.core import config
from app.core.config import settings
from app.core.exceptions import PaymentError
from app.models.enums import PaymentMethod
from app.models.order import Order, Payment

logger = logging.getLogger(__name__)

# 모의 가상계좌를 발급할 때 사용할 은행 목록
VBANK_BANKS = ["국민은행", "신한은행", "우리은행", "하나은행", "농협은행"]


class PgGateway(ABC):
    """PG사가 달라도 PaymentService가 같은 방식으로 호출하도록 정한 인터페이스."""

    @abstractmethod
    def approve(self, order: Order, payment: Payment, extra: Dict) -> Dict:
        """결제를 승인하고 공통 응답 형식으로 반환한다."""

    @abstractmethod
    def cancel(
        self,
        payment: Payment,
        amount: float,
        reason: str,
    ) -> Dict:
        """결제를 취소하고 공통 응답 형식으로 반환한다."""


class MockPgGateway(PgGateway):
    """PG 서버를 호출하지 않고 결제 성공 응답을 만들어 내는 개발·테스트용 게이트웨이."""

    @staticmethod
    def _tid() -> str:
        """모의 결제 거래 번호(TID)를 만든다."""
        random_text = "".join(
            random.choices(string.ascii_uppercase + string.digits, k=10)
        )
        return f"MOCK{datetime.now().strftime('%Y%m%d%H%M%S')}{random_text}"

    def approve(self, order: Order, payment: Payment, extra: Dict) -> Dict:
        """모의 결제 승인 결과를 만든다."""

        result = {
            "result_code": "0000",
            "result_msg": "정상 승인",
            "tid": self._tid(),
            "amount": float(payment.amount),
            "approved_at": datetime.now(timezone.utc).isoformat(),
        }

        if payment.method == PaymentMethod.CARD:
            # 카드 정보는 실제 카드가 아닌 테스트용 값을 사용한다.
            result.update(
                {
                    "card_name": extra.get("card_name") or "모의카드",
                    "card_no_masked": (
                        extra.get("card_no_masked") or "5555-****-****-1234"
                    ),
                    "receipt_url": (
                        "https://mock-pg.local/receipt/" + result["tid"]
                    ),
                }
            )

        elif payment.method == PaymentMethod.VBANK:
            # 가상계좌는 계좌 정보를 만들고 입금 대기 상태로 반환한다.
            result.update(
                {
                    "status": "READY",
                    "vbank_bank": random.choice(VBANK_BANKS),
                    "vbank_no": "".join(
                        random.choices(string.digits, k=14)
                    ),
                    "vbank_holder": "(주)북스토어",
                    "vbank_due": (
                        datetime.now(timezone.utc) + timedelta(days=3)
                    ).isoformat(),
                }
            )

        return result

    def cancel(
        self,
        payment: Payment,
        amount: float,
        reason: str,
    ) -> Dict:
        """모의 결제 취소 결과를 만든다."""
        return {
            "result_code": "0000",
            "result_msg": "취소 완료",
            "tid": payment.pg_tid,
            "cancel_amount": amount,
            "cancelled_at": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
        }


class TossPgGateway(PgGateway):
    """토스페이먼츠 API를 호출하는 실제 PG 게이트웨이."""

    APPROVE_URL = "https://api.tosspayments.com/v1/payments/confirm"
    CANCEL_URL = "https://api.tosspayments.com/v1/payments"

    # 토스 API 응답을 기다릴 최대 시간(초)
    TIMEOUT = 15

    @staticmethod
    def _headers() -> Dict[str, str]:
        """토스 API 인증에 필요한 헤더를 만든다."""

        secret_key = config.toss_secret_key()
        if not secret_key:
            raise PaymentError("TOSS_SECRET_KEY가 설정되지 않았습니다.")

        # 토스 인증 형식은 Base64("시크릿키:")를 Basic 인증 헤더로 전달하는 방식이다.
        import base64

        encoded_key = base64.b64encode(
            f"{secret_key}:".encode("utf-8")
        ).decode("utf-8")

        return {
            "Authorization": f"Basic {encoded_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _read_response(response: requests.Response) -> Dict:
        """토스 응답을 JSON으로 읽고, JSON이 아니면 빈 딕셔너리를 반환한다."""
        try:
            return response.json()
        except ValueError:
            return {}

    def _post(self, url: str, body: Dict) -> Dict:
        """토스에 POST 요청을 보내고 통신 오류를 PaymentError로 바꾼다."""

        try:
            response = requests.post(
                url,
                headers=self._headers(),
                json=body,
                timeout=self.TIMEOUT,
            )
        except requests.Timeout as exc:
            logger.error("토스페이먼츠 응답 지연: %s", url)
            raise PaymentError("결제 서버 응답이 지연되고 있습니다.") from exc
        except requests.RequestException as exc:
            logger.error("토스페이먼츠 연결 오류: %s", exc)
            raise PaymentError("결제 서버에 연결할 수 없습니다.") from exc

        result = self._read_response(response)

        # 토스의 정상 응답은 HTTP 200이다.
        if response.status_code == 200:
            return result

        # 실패 응답도 PaymentService가 처리할 수 있도록 공통 키로 바꾼다.
        return {
            "result_code": result.get("code") or str(response.status_code),
            "result_msg": result.get("message") or "토스페이먼츠 요청에 실패했습니다.",
            "raw_response": result,
        }

    def approve(self, order: Order, payment: Payment, extra: Dict) -> Dict:
        """
        프론트엔드가 토스 결제창에서 받은 payment_key로 최종 승인을 요청한다.

        extra에는 프론트엔드가 받은 payment_key가 들어 있어야 한다.
        """
        payment_key = extra.get("payment_key")
        if not payment_key:
            raise PaymentError(
                "토스 결제 승인에 필요한 payment_key가 없습니다."
            )

        # 토스가 승인하는 금액과 주문 번호는 서버 DB 값을 사용한다.
        # 프론트엔드가 보낸 금액을 그대로 승인 요청에 사용하지 않는다.
        response_data = self._post(
            self.APPROVE_URL,
            {
                "paymentKey": payment_key,
                "orderId": order.order_no,
                "amount": int(payment.amount),
            },
        )

        # 실패 응답은 PaymentService가 result_code로 판단할 수 있게 전달한다.
        if response_data.get("result_code"):
            return response_data

        # TossPaymentService의 응답을 기존 PaymentService가 쓰는 형식으로 변환한다.
        result = {
            "result_code": "0000",
            "result_msg": "정상 승인",
            "tid": response_data.get("paymentKey"),
            "amount": response_data.get("totalAmount", payment.amount),
            "approved_at": response_data.get("approvedAt"),
        }

        # 카드 결제 응답에서 카드와 영수증 정보를 가져온다.
        card = response_data.get("card") or {}
        receipt = response_data.get("receipt") or {}

        if payment.method == PaymentMethod.CARD:
            result.update(
                {
                    "card_name": (
                        card.get("company")
                        or card.get("issuerCode")
                        or "카드"
                    ),
                    "card_no_masked": card.get("number"),
                    "receipt_url": receipt.get("url"),
                }
            )

        # 가상계좌는 토스 응답의 virtualAccount 정보를 기존 형식으로 바꾼다.
        if payment.method == PaymentMethod.VBANK:
            virtual_account = response_data.get("virtualAccount") or {}

            result.update(
                {
                    "status": "READY",
                    "vbank_bank": virtual_account.get("bank"),
                    "vbank_no": virtual_account.get("accountNumber"),
                    "vbank_holder": virtual_account.get("customerName"),
                    "vbank_due": virtual_account.get("dueDate"),
                }
            )

        return result

    def cancel(
        self,
        payment: Payment,
        amount: float,
        reason: str,
    ) -> Dict:
        """토스에 결제 취소 또는 부분 취소를 요청한다."""

        if not payment.pg_tid:
            raise PaymentError("토스 결제 키(paymentKey)가 없습니다.")

        # Toss 결제 응답의 paymentKey를 기존 모델의 pg_tid 필드에 저장해 사용한다.
        url = f"{self.CANCEL_URL}/{payment.pg_tid}/cancel"

        response_data = self._post(
            url,
            {
                "cancelReason": reason,
                "cancelAmount": int(amount),
            },
        )

        if response_data.get("result_code"):
            return response_data

        return {
            "result_code": "0000",
            "result_msg": "취소 완료",
            "tid": payment.pg_tid,
            "cancel_amount": amount,
            "cancelled_at": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "raw_response": response_data,
        }


def get_gateway() -> PgGateway:
    """설정에 따라 모의 게이트웨이나 토스 게이트웨이를 선택한다."""

    if settings.PG_MOCK_MODE:
        return MockPgGateway()

    return TossPgGateway()