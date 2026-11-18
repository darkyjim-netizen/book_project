from types import SimpleNamespace
from unittest.mock import patch

import pytest

from team_backend.app.core.exceptions import PaymentError
from team_backend.app.models.enums import PaymentMethod
from team_backend.app.services.payment_gateway import TossPgGateway


def test_toss_approval_requires_matching_payment_details():
    order = SimpleNamespace(order_no="ORDER-123")
    payment = SimpleNamespace(amount=12000, method=PaymentMethod.CARD)
    gateway = TossPgGateway()
    result = {"paymentKey": "key", "orderId": "ORDER-123", "totalAmount": 12000, "status": "DONE"}
    with patch.object(gateway, "_post", return_value=result):
        assert gateway.approve(order, payment, {"payment_key": "key"})["tid"] == "key"
    with patch.object(gateway, "_post", return_value={**result, "totalAmount": 1}):
        with pytest.raises(PaymentError):
            gateway.approve(order, payment, {"payment_key": "key"})
