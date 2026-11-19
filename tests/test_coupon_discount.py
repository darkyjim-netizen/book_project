from decimal import Decimal

from app.models.enums import CouponType
from app.models.promotion import Coupon


def test_percent_coupon_respects_minimum_and_discount_limit():
    coupon = Coupon(
        coupon_type=CouponType.PERCENT,
        discount_value=Decimal('30'),
        min_order_amount=Decimal('10000'),
        max_discount=Decimal('5000'),
    )

    assert coupon.calc_discount(9999) == 0
    assert coupon.calc_discount(10000) == 3000
    assert coupon.calc_discount(20000) == 5000
