from types import SimpleNamespace

import pytest
from unittest.mock import Mock
from sqlalchemy import select
from fastapi.testclient import TestClient

from app.core.exceptions import BusinessError, NotFoundError
from app.models.enums import BookStatus
from app.models.order import Order
from app.schemas.order import OrderCreateRequest
from app.services.order_service import OrderService
from app.routers.orders import lookup_order_post
from app.schemas.order import GuestOrderLookupRequest
from app.core.database import get_db
from main import app


def test_guest_lookup_checks_order_number_email_and_guest_ownership(monkeypatch):
    orders = {'GUEST-1': SimpleNamespace(orderer_email='guest@example.com', member_id=None),
              'MEMBER-1': SimpleNamespace(orderer_email='guest@example.com', member_id=4)}
    db = Mock()
    monkeypatch.setattr(OrderService, '_query_with_relations', lambda self: select(Order))
    monkeypatch.setattr(OrderService, 'to_response', lambda self, order: order)
    for number, email in [('GUEST-1', 'GUEST@example.com'), ('GUEST-1', 'wrong@example.com'), ('MEMBER-1', 'guest@example.com'), ('MISSING', 'guest@example.com')]:
        db.scalar.return_value = orders.get(number)
        payload = GuestOrderLookupRequest(order_no=number, email=email)
        if number == 'GUEST-1' and email == 'GUEST@example.com':
            assert lookup_order_post(payload, db) is orders[number]
        else:
            with pytest.raises(NotFoundError, match='일치하는 비회원 주문'):
                lookup_order_post(payload, db)


def test_guest_cannot_use_member_coupon():
    service = OrderService(None)
    book = SimpleNamespace(status=BookStatus.SALE, stock_qty=2, sale_price=1000, list_price=1000)
    service._resolve_items = lambda member, payload, session: ([(book, 1)], [])
    payload = OrderCreateRequest(orderer_name='테스트', orderer_phone='010-1234-5678', orderer_email='guest@example.com', receiver='테스트', receiver_phone='010-1234-5678', zipcode='12345', address1='서울', member_coupon_id=1)
    with pytest.raises(BusinessError, match='쿠폰은 회원만'):
        service.create_order(None, payload)


def test_lookup_http_post(monkeypatch):
    from datetime import datetime, timezone
    db = Mock()
    db.scalar.return_value = SimpleNamespace(orderer_email='guest@example.com', member_id=None)
    monkeypatch.setattr(OrderService, '_query_with_relations', lambda self: select(Order))
    monkeypatch.setattr(OrderService, 'to_response', lambda self, order: {
        'order_id': 1, 'order_no': 'GUEST-1', 'status': 'PAID', 'status_label': '결제 완료',
        'summary_title': '테스트 도서', 'item_amount': 1000, 'discount_amount': 0,
        'coupon_amount': 0, 'point_used': 0, 'ship_fee': 0, 'total_amount': 1000,
        'point_saved': 0, 'orderer_name': '테스트', 'receiver': '테스트',
        'receiver_phone': '010-0000-0000', 'zipcode': '12345', 'address1': '서울',
        'ordered_at': datetime.now(timezone.utc), 'items': [],
    })
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            response = client.post('/api/v1/orders/lookup', json={'order_no': 'GUEST-1', 'email': 'guest@example.com'})
            assert response.status_code == 200
            assert response.json()['order_no'] == 'GUEST-1'
            response = client.post('/api/v1/orders/lookup', json={'order_no': 'GUEST-1', 'email': 'wrong@example.com'})
            assert response.status_code == 404
            db.scalar.return_value = SimpleNamespace(orderer_email='guest@example.com', member_id=5)
            response = client.post('/api/v1/orders/lookup', json={'order_no': 'GUEST-1', 'email': 'guest@example.com'})
            assert response.status_code == 404
            response = client.post('/api/v1/orders/lookup', json={'order_no': 'GUEST-1', 'email': 'invalid'})
            assert response.status_code == 422
    finally:
        app.dependency_overrides.pop(get_db, None)
