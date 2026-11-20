from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import FastAPI

from app.core.database import get_db
from app.core.security import require_admin
from app.routers.admin import router
from app.services.order_service import OrderService


def test_claims_route_is_not_parsed_as_order_id():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[require_admin] = lambda: SimpleNamespace(member_id=1)
    app.dependency_overrides[get_db] = lambda: Mock()
    with patch("app.routers.admin.OrderService") as service:
        service.return_value.list_all_orders.return_value = ([], 0)
        from starlette.routing import Match
        from app.models.enums import OrderStatus
        scope = {"type": "http", "path": "/admin/orders/claims", "method": "GET"}
        route = next(route for route in router.routes if route.matches(scope)[0] == Match.FULL)
        assert route.path == "/admin/orders/claims"
        result = route.endpoint(page=2, size=20, status_filter=OrderStatus.RETURN_REQ, keyword="test", _admin=None, db=Mock())
        assert result.items == []
        service.return_value.list_all_orders.assert_called_once_with(2, 20, "RETURN_REQ", "test", claims_only=True)


def test_claims_query_limits_both_rows_and_count():
    db = Mock()
    db.scalar.return_value = 0
    db.scalars.return_value.unique.return_value = []
    assert OrderService(db).list_all_orders(claims_only=True) == ([], 0)
    for statement in [db.scalar.call_args.args[0], db.scalars.call_args.args[0]]:
        values = statement.compile().params
        assert any(isinstance(value, list) and {s.value for s in value} == {"CANCELLED", "RETURN_REQ", "RETURNED", "EXCHANGE_REQ", "EXCHANGED"} for value in values.values())
