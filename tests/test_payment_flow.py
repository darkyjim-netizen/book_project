
#결제 플로우 통합 테스트 (책 6.5절 (5))

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from sqlalchemy import select

from app.models.order_model import OrderStatusHistory
from tests.conftest import make_member, order_input

from app.auth.jwt_tokens import issue_tokens
from app.crud.order_crud import place_order

HTTP_CLIENT = "app.services.payment_service.httpx.AsyncClient"
FAIL_URL = "http://localhost:8000/api/payments/toss/fail"


def toss_response(status_code: int, body: dict) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = body
    return response


def mock_toss(mock_http: MagicMock, response=None, error: Exception | None = None) -> AsyncMock:
    """httpx.AsyncClient의 post를 가짜로 바꾸고, 호출 내용을 확인할 수 있게 돌려줍니다."""
    post = AsyncMock(return_value=response, side_effect=error)
    mock_http.return_value.__aenter__.return_value.post = post
    return post


def success_url(order, amount=None, payment_key="test_payment_key") -> str:
    amount = order.total if amount is None else amount
    return f"/api/payments/toss/success?paymentKey={payment_key}&orderId={order.order_number}&amount={amount}"


def pay(client, order, payment_key="test_payment_key"):
    """주문을 결제 완료 상태로 만듭니다."""
    with patch(HTTP_CLIENT) as mock_http:
        mock_toss(mock_http, toss_response(200, {"paymentKey": payment_key, "status": "DONE"}))
        response = client.get(success_url(order, payment_key=payment_key))
    assert response.status_code == 303
    return response


# ── 결제창 초기화 데이터
def test_ready_data_uses_server_amount(client, auth_headers, sample_order):
    response = client.get(f"/api/payments/toss/{sample_order.id}/ready", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["client_key"] == "test_ck_pytest"
    assert data["order_id"] == sample_order.order_number
    assert data["order_name"] == "파이썬 책"
    assert data["amount"] == 30000
    assert data["success_url"] == "http://localhost:8000/api/payments/toss/success"
    assert data["fail_url"] == FAIL_URL
    # 비밀 키는 어떤 경우에도 응답에 들어가면 안 됩니다.
    assert "test_sk_pytest" not in response.text


def test_ready_requires_login_and_ownership(client, db, sample_order):
    assert client.get(f"/api/payments/toss/{sample_order.id}/ready").status_code == 401

    other = make_member(db, "other")
    headers = {"Authorization": f"Bearer {issue_tokens(other.id).access_token}"}
    assert client.get(f"/api/payments/toss/{sample_order.id}/ready", headers=headers).status_code == 404


# ── 결제 승인
def test_payment_amount_mismatch(client, db, sample_order):
    """금액 불일치 시 결제 거부 테스트"""
    fake_amount = sample_order.total - 1000  # 1,000원 낮게 조작

    with patch(HTTP_CLIENT) as mock_http:
        post = mock_toss(mock_http, toss_response(200, {}))
        response = client.get(success_url(sample_order, amount=fake_amount))

    # 금액 불일치 → PG사 호출 없이 결제 거부 → 실패 페이지로 리디렉션
    assert response.status_code == 303
    assert response.headers["location"].startswith(FAIL_URL)
    assert "PAYMENT_AMOUNT_MISMATCH" in response.headers["location"]
    post.assert_not_called()
    db.refresh(sample_order)
    assert sample_order.status == "pending"
    assert sample_order.payment_key is None


def test_payment_success_flow(client, db, sample_order):
    """정상 결제 승인 플로우 테스트 (PG사 API Mock)"""
    with patch(HTTP_CLIENT) as mock_http:
        post = mock_toss(mock_http, toss_response(200, {
            "paymentKey": "test_payment_key",
            "orderId": sample_order.order_number,
            "status": "DONE",
            "totalAmount": sample_order.total,
        }))
        response = client.get(success_url(sample_order))

    assert response.status_code == 303
    assert response.headers["location"] == f"http://localhost:5173/orders/{sample_order.id}/complete"

    # 토스 승인 API에 결제키·주문번호·금액과 Basic 인증 헤더를 보냈는지 확인합니다.
    args, kwargs = post.call_args
    assert args[0] == "https://api.tosspayments.com/v1/payments/confirm"
    assert kwargs["json"] == {"paymentKey": "test_payment_key", "orderId": sample_order.order_number,
                              "amount": 30000}
    assert kwargs["headers"]["Authorization"] == "Basic dGVzdF9za19weXRlc3Q6"  # base64("test_sk_pytest:")

    db.refresh(sample_order)
    assert sample_order.status == "paid"
    assert sample_order.payment_status == "paid"
    assert sample_order.payment_key == "test_payment_key"
    assert sample_order.paid_at is not None

    history = db.scalars(select(OrderStatusHistory.to_status)
                         .where(OrderStatusHistory.order_id == sample_order.id)
                         .order_by(OrderStatusHistory.id)).all()
    assert history == ["pending", "payment_wait", "paid"]


def test_repeated_success_callback_does_not_confirm_twice(client, db, sample_order):
    pay(client, sample_order)

    with patch(HTTP_CLIENT) as mock_http:
        post = mock_toss(mock_http, toss_response(200, {}))
        response = client.get(success_url(sample_order))

    assert response.status_code == 303
    assert response.headers["location"].endswith(f"/orders/{sample_order.id}/complete")
    post.assert_not_called()


def test_payment_rejected_by_pg_cancels_order_and_restores_stock(client, db, sample_order, product):
    db.refresh(product)
    assert product.stock == 8

    with patch(HTTP_CLIENT) as mock_http:
        mock_toss(mock_http, toss_response(400, {"code": "REJECT_CARD_COMPANY", "message": "카드사 거절"}))
        response = client.get(success_url(sample_order))

    assert response.status_code == 303
    assert response.headers["location"].startswith(FAIL_URL)
    assert "PAYMENT_FAILED" in response.headers["location"]
    db.refresh(sample_order)
    db.refresh(product)
    assert sample_order.status == "cancelled"
    assert sample_order.payment_key is None
    assert product.stock == 10


def test_payment_timeout_redirects_to_fail_page(client, db, sample_order):
    with patch(HTTP_CLIENT) as mock_http:
        mock_toss(mock_http, error=httpx.TimeoutException("timeout"))
        response = client.get(success_url(sample_order))

    assert response.status_code == 303
    assert "PAYMENT_TIMEOUT" in response.headers["location"]
    db.refresh(sample_order)
    assert sample_order.status == "payment_wait"


def test_unknown_order_number_redirects_to_fail_page(client, db):
    response = client.get("/api/payments/toss/success?paymentKey=k&orderId=ORD-NOPE&amount=1000")

    assert response.status_code == 303
    assert "ORDER_NOT_FOUND" in response.headers["location"]


# ── 결제 실패 페이지
def test_fail_page_shows_message_escaped(client, db):
    response = client.get("/api/payments/toss/fail", params={
        "code": "PAY_PROCESS_CANCELED", "message": "<script>alert(1)</script>사용자가 결제를 취소했습니다",
        "orderId": "ORD-1"})

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "PAY_PROCESS_CANCELED" in response.text
    assert "사용자가 결제를 취소했습니다" in response.text
    assert "<script>alert(1)</script>" not in response.text


def test_failure_redirect_can_be_followed_to_fail_page(client, db, sample_order):
    with patch(HTTP_CLIENT) as mock_http:
        mock_toss(mock_http, toss_response(400, {"message": "카드사 거절"}))
        redirect = client.get(success_url(sample_order))

    page = client.get(redirect.headers["location"])
    assert page.status_code == 200
    assert "결제 실패: 카드사 거절" in page.text
    assert sample_order.order_number in page.text


# ── 결제 취소
def test_cancel_before_payment_changes_db_only(client, db, auth_headers, sample_order, product):
    with patch(HTTP_CLIENT) as mock_http:
        post = mock_toss(mock_http, toss_response(200, {}))
        response = client.post(f"/api/payments/{sample_order.id}/cancel", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "결제 전 취소 완료"}
    post.assert_not_called()
    db.refresh(sample_order)
    db.refresh(product)
    assert sample_order.status == "cancelled"
    assert product.stock == 10


def test_cancel_after_payment_calls_pg_and_refunds(client, db, auth_headers, sample_order, product):
    pay(client, sample_order)

    with patch(HTTP_CLIENT) as mock_http:
        post = mock_toss(mock_http, toss_response(200, {"status": "CANCELED"}))
        response = client.post(f"/api/payments/{sample_order.id}/cancel", headers=auth_headers,
                               params={"cancel_reason": "단순 변심"})

    assert response.status_code == 200
    assert response.json() == {"success": True, "cancel_data": {"status": "CANCELED"}}
    args, kwargs = post.call_args
    assert args[0] == "https://api.tosspayments.com/v1/payments/test_payment_key/cancel"
    # 전액 취소만 지원하므로 cancelAmount는 보내지 않습니다.
    assert kwargs["json"] == {"cancelReason": "단순 변심"}

    db.refresh(sample_order)
    db.refresh(product)
    assert sample_order.status == "refunded"
    assert product.stock == 10
    last = db.scalars(select(OrderStatusHistory).where(OrderStatusHistory.order_id == sample_order.id)
                      .order_by(OrderStatusHistory.id.desc())).first()
    assert (last.from_status, last.to_status, last.reason) == ("paid", "refunded", "단순 변심")


def test_cancel_failure_from_pg_keeps_order_paid(client, db, auth_headers, sample_order, product):
    pay(client, sample_order)

    with patch(HTTP_CLIENT) as mock_http:
        mock_toss(mock_http, toss_response(400, {"message": "이미 취소된 결제입니다."}))
        response = client.post(f"/api/payments/{sample_order.id}/cancel", headers=auth_headers)

    assert response.status_code == 400
    assert response.json() == {"code": "PAYMENT_CANCEL_FAILED", "message": "결제 취소 실패: 이미 취소된 결제입니다."}
    db.refresh(sample_order)
    db.refresh(product)
    assert sample_order.status == "paid"
    assert product.stock == 8


def test_cancel_twice_is_rejected_without_calling_pg(client, db, auth_headers, sample_order):
    pay(client, sample_order)
    with patch(HTTP_CLIENT) as mock_http:
        mock_toss(mock_http, toss_response(200, {}))
        assert client.post(f"/api/payments/{sample_order.id}/cancel", headers=auth_headers).status_code == 200

    with patch(HTTP_CLIENT) as mock_http:
        post = mock_toss(mock_http, toss_response(200, {}))
        response = client.post(f"/api/payments/{sample_order.id}/cancel", headers=auth_headers)

    assert response.status_code == 409
    assert response.json()["code"] == "INVALID_ORDER_STATUS"
    post.assert_not_called()


def test_cancel_requires_login_and_ownership(client, db, sample_order):
    assert client.post(f"/api/payments/{sample_order.id}/cancel").status_code == 401

    other = make_member(db, "other")
    headers = {"Authorization": f"Bearer {issue_tokens(other.id).access_token}"}
    response = client.post(f"/api/payments/{sample_order.id}/cancel", headers=headers)
    assert response.status_code == 404
    db.refresh(sample_order)
    assert sample_order.status == "pending"


# ── 기존 주문 API
def test_order_api_creates_pending_toss_order(client, db, auth_headers, product):
    response = client.post("/api/orders", headers=auth_headers, json={
        "receiver_name": "홍길동", "address": "서울특별시 강남구 테헤란로 123",
        "payment_info": {"method": "toss"}, "items": [{"product_id": product.id, "quantity": 1}]})

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "pending"
    assert data["payment_method"] == "toss"
    assert data["order_number"].startswith("ORD-")
    assert data["paid_at"] is None


def test_test_payment_order_still_completes_immediately(db, member, product):
    order = place_order(db, member.id, order_input(product, "test"))

    assert order.status == "paid"
    assert order.payment_status == "test_paid"
    assert order.payment_method == "test"
    assert order.paid_at is not None
