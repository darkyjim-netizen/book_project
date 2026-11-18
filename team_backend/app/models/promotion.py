"""쿠폰 / 배너 ORM 모델."""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum as PgEnum,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    func,
)
# Mapped는 파이썬에서 사용할 자료형을, mapped_column은 DB 컬럼 설정을 나타낸다.
from sqlalchemy.orm import Mapped, mapped_column, relationship

from team_backend.app.core.database import Base
from team_backend.app.models.enums import CouponType


# 여러 회원에게 발급할 수 있는 쿠폰의 공통 할인 조건을 정의한다.
class Coupon(Base):
    """쿠폰의 할인 조건, 발급 수량, 유효기간을 저장한다."""

    # 테이블 이름과 스키마 이름을 합쳐 DB의 shop.coupons를 가리킨다.
    __tablename__ = "coupons"
    __table_args__ = {"schema": "shop"}

    # 기본 키는 쿠폰마다 하나씩 부여되는 고유 번호다.
    coupon_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # unique=True는 중복 쿠폰 코드를 막고, nullable=False는 값이 꼭 필요하다는 뜻이다.
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # 할인 방식은 정액(AMOUNT), 정률(PERCENT), 무료 배송(FREESHIP) 중 하나다.
    coupon_type: Mapped[CouponType] = mapped_column(
        PgEnum(CouponType, name="coupon_type", schema="shop", create_type=False)
    )

    # discount_value는 쿠폰 유형에 따라 정액 할인 금액 또는 할인율을 뜻한다.
    # Numeric(10, 2)는 전체 자릿수가 최대 10자리이며, 그중 2자리가 소수점 아래다.
    discount_value: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    # 정률 할인 상한은 비워 둘 수 있다. 최소 주문 금액을 생략하면 기본값은 0이다.
    max_discount: Mapped[Optional[float]] = mapped_column(Numeric(10, 0))
    min_order_amount: Mapped[float] = mapped_column(Numeric(12, 0), default=0)
    # 외래 키로 카테고리를 연결한다. Optional은 이 번호를 비워 둘 수 있다는 뜻이다.
    category_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("shop.categories.category_id")
    )

    # 전체 발급 가능 수량과 이미 발급한 수량을 각각 기록한다.
    # 발급 가능 수량을 비워 두면 발급 한도가 없다는 뜻이다.
    total_quantity: Mapped[Optional[int]] = mapped_column(Integer)
    issued_count: Mapped[int] = mapped_column(Integer, default=0)
    # 시작 시각을 생략하면 DB의 현재 시각을 사용한다. 종료 시각은 필수다.
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    valid_to: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    # SQLAlchemy가 새 쿠폰을 저장할 때 이 값을 생략하면 활성 상태로 저장한다.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def calc_discount(self, order_amount: float) -> int:
        """주문 금액에 대한 할인액을 정수로 반환한다."""
        # 최소 주문 금액에 미달하면 할인을 적용하지 않는다.
        if order_amount < float(self.min_order_amount):
            return 0

        # 정액 할인은 주문 금액을 넘지 않도록 제한한다.
        if self.coupon_type == CouponType.AMOUNT:
            # 예를 들어 5,000원 쿠폰을 3,000원 주문에 쓰면 3,000원을 할인한다.
            return int(min(float(self.discount_value), order_amount))

        # 정률 할인은 할인율로 계산하고, 상한이 설정되어 있으면 적용한다.
        if self.coupon_type == CouponType.PERCENT:
            # 예를 들어 20,000원에 10%를 적용하면 2,000원이다.
            raw = order_amount * float(self.discount_value) / 100.0
            if self.max_discount:
                raw = min(raw, float(self.max_discount))
            # int()는 소수점 아래를 버려 정수 금액을 돌려준다.
            return int(raw)

        # 무료 배송 쿠폰(FREESHIP)은 배송비 계산에서 처리한다.
        return 0


# 같은 쿠폰을 여러 회원이 받아도 발급·사용 기록은 회원별로 저장한다.
class MemberCoupon(Base):
    """회원에게 발급된 쿠폰의 사용 여부와 만료 시각을 저장한다."""

    __tablename__ = "member_coupons"
    __table_args__ = {"schema": "shop"}

    member_coupon_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # 회원 번호와 원본 쿠폰 번호를 연결한다. CASCADE는 해당 회원이나 쿠폰이
    # 삭제되면 연결된 발급 기록도 DB에서 함께 삭제한다는 뜻이다.
    member_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("shop.members.member_id", ondelete="CASCADE")
    )
    # 기본 키는 쿠폰마다 하나씩 부여되는 고유 번호다.
    coupon_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("shop.coupons.coupon_id", ondelete="CASCADE")
    )

    # 쿠폰을 사용한 주문을 연결할 수 있다.
    # 아직 사용하지 않은 쿠폰에는 주문 번호를 비워 둘 수 있다.
    order_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("shop.orders.order_id")
    )
    # 발급 직후에는 미사용 상태다. 실제로 사용한 시각은 used_at에 따로 저장한다.
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    # 이 발급 기록의 만료 시각이다. 원본 쿠폰의 종료 시각은 Coupon.valid_to에 있다.
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # 회원 쿠폰을 조회할 때 원본 쿠폰 정보도 JOIN으로 함께 불러온다.
    # JOIN은 연결된 테이블을 한 번의 조회로 가져온다. 예를 들어 member_coupon.coupon.name으로 이름을 읽는다.
    coupon: Mapped["Coupon"] = relationship(lazy="joined")


# 화면에 보여 줄 배너 한 개의 표시 정보를 저장한다.
class Banner(Base):
    """배너의 이미지, 이동 링크, 노출 위치와 기간을 저장한다."""

    __tablename__ = "banners"
    __table_args__ = {"schema": "shop"}

    banner_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # 위치를 생략하면 메인 화면 상단(MAIN_TOP)으로 저장한다.
    position: Mapped[str] = mapped_column(String(30), default="MAIN_TOP")
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    image_url: Mapped[str] = mapped_column(String(255), nullable=False)
    # 클릭 시 이동할 주소가 없으면 비워 둘 수 있다.
    link_url: Mapped[Optional[str]] = mapped_column(String(255))
    # sort_order는 배너 표시 순서에 쓰는 값이고, is_active는 활성화 여부다.
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=0)
    # SQLAlchemy가 새 쿠폰을 저장할 때 이 값을 생략하면 활성 상태로 저장한다.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # 노출 시작 시각은 기본적으로 등록 시각이며, 종료 시각은 비워 둘 수 있다.
    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
