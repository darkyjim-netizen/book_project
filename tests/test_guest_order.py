from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from team_backend.app.core.exceptions import BusinessError, NotFoundError
from team_backend.app.models.order import Order
from team_backend.app.models.enums import BookStatus
from team_backend.app.schemas.order import OrderCreateRequest
from team_backend.app.services.order_service import OrderService


def test_guest_lookup_checks_order_number_email_and_guest_ownership():
    engine = create_engine('sqlite://')
    with engine.begin() as conn:
        conn.execute(text("ATTACH DATABASE ':memory:' AS shop"))
        conn.execute(text('CREATE TABLE shop.orders (order_no TEXT, orderer_email TEXT, member_id INTEGER)'))
        conn.execute(text("INSERT INTO shop.orders VALUES ('GUEST-1', 'guest@example.com', NULL), ('MEMBER-1', 'guest@example.com', 4)"))
    with Session(engine) as db:
        service = OrderService(db)
        service._query_with_relations = lambda: select(Order.order_no)
        assert service.get_by_order_no('GUEST-1', 'GUEST@example.com') == 'GUEST-1'
        for number, email in [('GUEST-1', 'wrong@example.com'), ('MEMBER-1', 'guest@example.com'), ('MISSING', 'guest@example.com')]:
            with pytest.raises(NotFoundError, match='일치하는 비회원 주문'):
                service.get_by_order_no(number, email)


def test_guest_cannot_use_member_coupon():
    service = OrderService(None)
    book = SimpleNamespace(status=BookStatus.SALE, stock_qty=2, sale_price=1000, list_price=1000)
    service._resolve_items = lambda member, payload: [(book, 1)]
    payload = OrderCreateRequest(orderer_name='테스트', orderer_phone='010-1234-5678', orderer_email='guest@example.com', receiver='테스트', receiver_phone='010-1234-5678', zipcode='12345', address1='서울', member_coupon_id=1)
    with pytest.raises(BusinessError, match='쿠폰은 회원만'):
        service.create_order(None, payload)
