from types import SimpleNamespace
from unittest.mock import Mock, patch
import pytest
from app.core.exceptions import BusinessError
from app.models.enums import PaymentStatus
from app.routers.admin import admin_cancel_order


def test_paid_cancel_calls_gateway_before_order_cleanup():
    db=Mock()
    payment=SimpleNamespace(payment_id=7,status=PaymentStatus.PARTIAL_CANCELLED,amount=10000,cancelled_amount=2000)
    order=SimpleNamespace(is_cancelable=True,main_payment=payment,point_used=0)
    with patch('app.routers.admin.OrderService') as orders, patch('app.services.payment_service.PaymentService') as payments:
        orders.return_value.get_order.return_value=order
        admin_cancel_order(1,'관리자 취소',None,db)
        payments.return_value.cancel_payment.assert_called_once_with(1,8000.0,'관리자 취소')
        orders.return_value.cancel_order.assert_called_once_with(1,None,'ADMIN_CANCEL','관리자 취소')
        refund=db.add.call_args.args[0]
        assert float(refund.refund_amount)==8000


def test_invalid_cancel_does_not_call_gateway():
    db=Mock()
    with patch('app.routers.admin.OrderService') as orders, patch('app.services.payment_service.PaymentService') as payments:
        orders.return_value.get_order.return_value=SimpleNamespace(is_cancelable=False)
        with pytest.raises(BusinessError):
            admin_cancel_order(1,'취소',None,db)
        payments.assert_not_called()


def test_failed_payment_cancel_does_not_restore_order():
    db=Mock()
    payment=SimpleNamespace(payment_id=7,status=PaymentStatus.PAID,amount=10000,cancelled_amount=0)
    with patch('app.routers.admin.OrderService') as orders, patch('app.services.payment_service.PaymentService') as payments:
        orders.return_value.get_order.return_value=SimpleNamespace(is_cancelable=True,main_payment=payment,point_used=0)
        payments.return_value.cancel_payment.side_effect=BusinessError('환불 실패')
        with pytest.raises(BusinessError):
            admin_cancel_order(1,'취소',None,db)
        orders.return_value.cancel_order.assert_not_called()
        db.add.assert_not_called()
