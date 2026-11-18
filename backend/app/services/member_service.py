"""회원 정보, 배송지, 포인트, 쿠폰을 관리하는 서비스."""
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import BusinessError, NotFoundError
from app.models.cart import Wishlist
from app.models.enums import MemberStatus, PointReason
from app.models.member import Member, MemberAddress, MemberGrade, PointHistory
from app.models.promotion import Coupon, MemberCoupon
from app.models.review import Review
from app.schemas.member import (
    AddressCreateRequest,
    MemberStatsResponse,
    MemberUpdateRequest,
)

logger = logging.getLogger(__name__)


class MemberService:
    """회원 관련 DB 작업과 업무 규칙을 처리한다."""

    def __init__(self, db: Session):
        self.db = db  # 서비스 메서드가 사용할 DB 세션

    # ------------------------------------------------------------------ 기본
    def get_member(self, member_id: int) -> Member:
        """회원 번호로 회원을 조회한다."""
        member = self.db.get(Member, member_id)  # 기본 키로 조회
        if member is None:
            raise NotFoundError("회원을 찾을 수 없습니다.")
        return member

    def update_profile(self, member: Member, payload: MemberUpdateRequest) -> Member:
        """요청에 포함된 회원 정보만 수정한다."""

        # exclude_unset=True는 요청에서 실제로 보낸 항목만 가져온다.
        # setattr은 member 객체의 해당 속성에 새 값을 넣는다.
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(member, key, value)

        self.db.commit()  # 수정 사항을 DB에 확정한다.
        self.db.refresh(member)  # DB에 저장된 최신 값으로 객체를 갱신한다.
        return member

    def my_stats(self, member: Member) -> MemberStatsResponse:
        """마이페이지에 표시할 회원 요약 정보를 계산한다."""
        # 주문 통계는 주문 서비스를 이용해 가져온다.
        # 함수 안에서 import해 서비스 간 순환 import를 피한다.
        from app.services.order_service import OrderService

        order_stats = OrderService(self.db).member_order_stats(member.member_id)

        # 아직 사용하지 않았고 만료되지 않은 회원 쿠폰 수를 센다.
        coupon_count = (
            self.db.scalar(
                select(func.count())
                .select_from(MemberCoupon)
                .where(
                    MemberCoupon.member_id == member.member_id,
                    MemberCoupon.is_used == False,  # noqa: E712
                    MemberCoupon.expires_at > datetime.now(timezone.utc),
                )
            )
            or 0  # 조회 결과가 None이면 0으로 처리한다.
        )

        # 회원이 작성한 리뷰 수
        review_count = (
            self.db.scalar(
                select(func.count())
                .select_from(Review)
                .where(Review.member_id == member.member_id)
            )
            or 0
        )

        # 회원의 위시리스트 항목 수
        wishlist_count = (
            self.db.scalar(
                select(func.count())
                .select_from(Wishlist)
                .where(Wishlist.member_id == member.member_id)
            )
            or 0
        )

        # 현재 누적 결제액보다 최소 구매 금액이 큰 등급 중 가장 가까운 등급을 찾는다.
        next_grade = self.db.scalar(
            select(MemberGrade)
            .where(MemberGrade.min_amount > float(member.total_paid))
            .order_by(MemberGrade.min_amount.asc())
            .limit(1)
        )

        # 각 통계 결과를 마이페이지 응답 스키마에 담는다.
        return MemberStatsResponse(
            order_count=int(order_stats.get("total") or 0),
            shipping_count=int(order_stats.get("shipping") or 0),
            point_balance=member.point_balance,
            coupon_count=coupon_count,
            review_count=review_count,
            wishlist_count=wishlist_count,
            grade_name=member.grade.grade_name if member.grade else "브론즈",
            next_grade_name=next_grade.grade_name if next_grade else None,
            next_grade_remain=(
                float(next_grade.min_amount) - float(member.total_paid)
                if next_grade
                else None
            ),
        )

    # ------------------------------------------------------------------ 배송지
    def list_addresses(self, member: Member) -> List[MemberAddress]:
        """회원의 배송지를 기본 배송지 우선, 최신 등록 순으로 조회한다."""
        return list(
            self.db.scalars(
                select(MemberAddress)
                .where(MemberAddress.member_id == member.member_id)
                .order_by(
                    MemberAddress.is_default.desc(),
                    MemberAddress.created_at.desc(),
                )
            ).unique()
        )

    def create_address(
        self,
        member: Member,
        payload: AddressCreateRequest,
    ) -> MemberAddress:
        """배송지를 등록한다. 첫 배송지는 기본 배송지로 지정한다."""

        # 회원이 이미 등록한 배송지 수를 확인한다.
        count = (
            self.db.scalar(
                select(func.count())
                .select_from(MemberAddress)
                .where(MemberAddress.member_id == member.member_id)
            )
            or 0
        )
        if count >= 10:
            raise BusinessError("배송지는 최대 10개까지 등록할 수 있습니다.")

        # 사용자가 기본 배송지로 지정했거나 첫 배송지라면 기본값으로 만든다.
        is_default = payload.is_default or count == 0

        if is_default:
            # 새 기본 배송지를 지정하기 전에 기존 기본 배송지 표시를 해제한다.
            self.db.query(MemberAddress).filter(
                MemberAddress.member_id == member.member_id
            ).update(
                {MemberAddress.is_default: False},
                synchronize_session=False,
            )

        # 요청 스키마를 딕셔너리로 바꿔 배송지 객체를 만든다.
        data = payload.model_dump()
        data["is_default"] = is_default
        address = MemberAddress(**data, member_id=member.member_id)

        self.db.add(address)
        self.db.commit()
        self.db.refresh(address)
        return address

    def update_address(
        self,
        address_id: int,
        member: Member,
        payload: AddressCreateRequest,
    ) -> MemberAddress:
        """회원 본인의 배송지를 수정한다."""

        address = self.db.get(MemberAddress, address_id)

        # 배송지가 없거나 다른 회원 소유라면 찾을 수 없다고 처리한다.
        if address is None or address.member_id != member.member_id:
            raise NotFoundError("배송지를 찾을 수 없습니다.")

        if payload.is_default:
            # 이 배송지를 기본 배송지로 만들기 전에 기존 기본값을 해제한다.
            self.db.query(MemberAddress).filter(
                MemberAddress.member_id == member.member_id
            ).update(
                {MemberAddress.is_default: False},
                synchronize_session=False,
            )

        # 전달된 배송지 데이터를 객체의 각 필드에 반영한다.
        for key, value in payload.model_dump().items():
            setattr(address, key, value)

        self.db.commit()
        self.db.refresh(address)
        return address

    def delete_address(self, address_id: int, member: Member) -> None:
        """회원 본인의 배송지를 삭제한다."""

        address = self.db.get(MemberAddress, address_id)
        if address is None or address.member_id != member.member_id:
            raise NotFoundError("배송지를 찾을 수 없습니다.")

        self.db.delete(address)
        self.db.commit()

    # ------------------------------------------------------------------ 포인트
    def list_points(
        self,
        member: Member,
        page: int = 1,
        size: int = 20,
    ) -> Tuple[List[PointHistory], int]:
        """포인트 내역을 최신순으로 페이지 조회한다."""

        # 페이지와 관계없이 전체 내역 수를 먼저 센다.
        total = (
            self.db.scalar(
                select(func.count())
                .select_from(PointHistory)
                .where(PointHistory.member_id == member.member_id)
            )
            or 0
        )

        # offset은 앞에서 건너뛸 행 수다.
        # 예: page=2, size=20이면 처음 20개를 건너뛰고 다음 20개를 가져온다.
        rows = list(
            self.db.scalars(
                select(PointHistory)
                .where(PointHistory.member_id == member.member_id)
                .order_by(PointHistory.created_at.desc())
                .offset((page - 1) * size)
                .limit(size)
            ).unique()
        )
        return rows, total

    def adjust_point(
        self,
        member_id: int,
        amount: int,
        memo: str,
        reason: PointReason = PointReason.ADMIN_ADJUST,
    ) -> Member:
        """관리자가 회원 포인트를 직접 조정하고 이력을 남긴다."""

        member = self.get_member(member_id)
        after = member.point_balance + amount  # 조정 후 포인트 잔액

        if after < 0:
            raise BusinessError("포인트 잔액이 0보다 작아질 수 없습니다.")

        member.point_balance = after

        # 현재 잔액만 바꾸는 게 아니라 조정 내역도 기록한다.
        self.db.add(
            PointHistory(
                member_id=member_id,
                reason=reason,
                amount=amount,
                balance_after=after,
                memo=memo,
            )
        )

        self.db.commit()
        self.db.refresh(member)
        logger.info("포인트 조정: member_id=%s amount=%s", member_id, amount)
        return member

    def expire_points(self, days: int = 365) -> int:
        """만료일이 지난 적립 포인트를 소멸시키는 배치 작업."""

        # 만료된 적립 포인트를 회원별로 합산한다.
        # 사용 또는 취소된 포인트가 이 합계에 어떻게 반영되는지는
        # 포인트 적립·사용 정책과 데이터 구조에 따라 확인해야 한다.
        sql = text(
            """
            SELECT member_id, COALESCE(SUM(amount), 0) AS expire_amount
              FROM shop.point_histories
             WHERE amount > 0 AND expires_at IS NOT NULL AND expires_at < now()
               AND reason IN ('ORDER_SAVE','REVIEW','EVENT')
             GROUP BY member_id
            """
        )
        rows = self.db.execute(sql).mappings().all()

        count = 0  # 포인트 소멸 처리를 한 회원 수
        for row in rows:
            member = self.db.get(Member, row["member_id"])
            if member is None:
                continue

            # 소멸 예정액이 현재 보유 잔액보다 크면 잔액까지만 소멸시킨다.
            amount = min(int(row["expire_amount"]), member.point_balance)
            if amount <= 0:
                continue

            member.point_balance -= amount

            # 소멸도 포인트 변동 내역으로 남긴다. 음수는 차감이라는 뜻이다.
            self.db.add(
                PointHistory(
                    member_id=member.member_id,
                    reason=PointReason.EXPIRE,
                    amount=-amount,
                    balance_after=member.point_balance,
                    memo="유효기간 만료 소멸",
                )
            )
            count += 1

        self.db.commit()
        return count

    # ------------------------------------------------------------------ 쿠폰
    def list_coupons(
        self,
        member: Member,
        include_used: bool = False,
    ) -> List[MemberCoupon]:
        """회원 쿠폰을 만료 시각이 가까운 순으로 조회한다."""

        # 기본적으로 해당 회원의 쿠폰만 찾는다.
        conditions = [MemberCoupon.member_id == member.member_id]

        if not include_used:
            # include_used가 False면 미사용이며 만료되지 않은 쿠폰만 조회한다.
            conditions.append(MemberCoupon.is_used == False)  # noqa: E712
            conditions.append(
                MemberCoupon.expires_at > datetime.now(timezone.utc)
            )

        return list(
            self.db.scalars(
                select(MemberCoupon)
                # 쿠폰 정보를 함께 불러와 응답할 때 추가 조회를 줄인다.
                .options(selectinload(MemberCoupon.coupon))
                .where(*conditions)
                .order_by(MemberCoupon.expires_at.asc())
            ).unique()
        )

    def issue_coupon(self, member: Member, code: str) -> MemberCoupon:
        """회원이 입력한 쿠폰 코드를 확인하고 쿠폰을 발급한다."""

        # 앞뒤 공백을 제거하고 대문자로 바꾼 코드로 검색한다.
        coupon = self.db.scalar(
            select(Coupon).where(Coupon.code == code.strip().upper())
        )
        if coupon is None or not coupon.is_active:
            raise NotFoundError("사용할 수 없는 쿠폰 코드입니다.")

        now = datetime.now(timezone.utc)
        if coupon.valid_to < now:
            raise BusinessError("유효기간이 지난 쿠폰입니다.")

        # 발급 수량 제한이 있고 이미 모두 발급했다면 중단한다.
        if (
            coupon.total_quantity is not None
            and coupon.issued_count >= coupon.total_quantity
        ):
            raise BusinessError("쿠폰이 모두 소진되었습니다.")

        # 이 회원이 같은 쿠폰을 이미 발급받았는지 확인한다.
        exists = self.db.scalar(
            select(MemberCoupon).where(
                MemberCoupon.member_id == member.member_id,
                MemberCoupon.coupon_id == coupon.coupon_id,
            )
        )
        if exists:
            raise BusinessError("이미 발급받은 쿠폰입니다.")

        # 회원별 쿠폰 발급 기록을 만들고 전체 발급 수를 늘린다.
        member_coupon = MemberCoupon(
            member_id=member.member_id,
            coupon_id=coupon.coupon_id,
            expires_at=coupon.valid_to,
        )
        self.db.add(member_coupon)
        coupon.issued_count += 1

        self.db.commit()
        self.db.refresh(member_coupon)
        return member_coupon

    def available_coupons_for_amount(
        self,
        member: Member,
        amount: float,
    ) -> List[dict]:
        """주문 금액에 사용할 수 있는 쿠폰과 예상 할인액을 계산한다."""

        result = []
        for mc in self.list_coupons(member):
            # 쿠폰 모델의 계산 함수로 정액·정률 할인액을 계산한다.
            discount = mc.coupon.calc_discount(amount)

            # 무료 배송 쿠폰은 상품 금액 할인액이 0이어도 결과에 포함한다.
            if mc.coupon.coupon_type.value == "FREESHIP" or discount > 0:
                result.append(
                    {
                        "member_coupon_id": mc.member_coupon_id,
                        "name": mc.coupon.name,
                        "coupon_type": mc.coupon.coupon_type.value,
                        "discount_amount": discount,
                        "expires_at": mc.expires_at,
                    }
                )

        # 예상 할인액이 큰 쿠폰부터 반환한다.
        return sorted(
            result,
            key=lambda x: x["discount_amount"],
            reverse=True,
        )

    # ------------------------------------------------------------------ 관리자
    def list_members(
        self,
        page: int = 1,
        size: int = 20,
        keyword: Optional[str] = None,
        status: Optional[str] = None,
        grade_id: Optional[int] = None,
    ) -> Tuple[List[Member], int]:
        """관리자용 회원 목록과 전체 검색 결과 수를 반환한다."""

        conditions = []

        if keyword:
            # 이름, 이메일, 전화번호 중 검색어가 포함된 회원을 찾는다.
            # ilike는 대소문자를 구분하지 않는 부분 검색이다.
            kw = f"%{keyword}%"
            conditions.append(
                or_(
                    Member.name.ilike(kw),
                    Member.email.ilike(kw),
                    Member.phone.ilike(kw),
                )
            )

        if status:
            # 문자열 상태를 MemberStatus Enum으로 바꿔 조건에 사용한다.
            conditions.append(Member.status == MemberStatus(status))

        if grade_id:
            conditions.append(Member.grade_id == grade_id)

        # 현재 페이지와 무관한 전체 검색 결과 수
        total = (
            self.db.scalar(
                select(func.count())
                .select_from(Member)
                .where(*conditions)
            )
            or 0
        )

        # 최신 가입 회원부터 페이지 단위로 가져온다.
        rows = list(
            self.db.scalars(
                select(Member)
                .where(*conditions)
                .order_by(Member.created_at.desc())
                .offset((page - 1) * size)
                .limit(size)
            ).unique()
        )
        return rows, total

    def change_status(self, member_id: int, status: str) -> Member:
        """관리자가 회원 상태를 변경한다."""

        member = self.get_member(member_id)
        member.status = MemberStatus(status)

        # 정지 해제 등으로 정상 상태가 되면 로그인 실패 횟수도 초기화한다.
        if member.status == MemberStatus.ACTIVE:
            member.login_fail_cnt = 0

        self.db.commit()
        self.db.refresh(member)
        return member

    def mark_dormant(self, days: int = 365) -> int:
        """오랫동안 로그인하지 않은 회원을 휴면 상태로 바꾸는 배치 작업."""

        # 현재 시각에서 기준 일수를 뺀 날짜를 휴면 판단 기준으로 삼는다.
        deadline = datetime.now(timezone.utc) - timedelta(days=days)

        # 정상 상태이면서 마지막 로그인 시각이 기준보다 오래됐거나,
        # 로그인 기록은 없지만 가입일도 기준보다 오래된 회원을 휴면 처리한다.
        updated = (
            self.db.query(Member)
            .filter(
                Member.status == MemberStatus.ACTIVE,
                or_(
                    Member.last_login_at < deadline,
                    Member.last_login_at.is_(None),
                ),
                Member.created_at < deadline,
            )
            .update(
                {Member.status: MemberStatus.DORMANT},
                synchronize_session=False,
            )
        )

        self.db.commit()
        return updated  # 휴면으로 바뀐 회원 수

    def refresh_all_grades(self) -> int:
        """DB 함수를 호출해 전체 회원의 등급을 다시 계산한다."""

        # 모든 회원 번호를 가져온다.
        ids = [
            row[0]
            for row in self.db.execute(select(Member.member_id))
        ]

        # 각 회원마다 DB에 정의된 등급 갱신 함수를 실행한다.
        for mid in ids:
            self.db.execute(
                text("SELECT shop.fn_refresh_member_grade(:mid)"),
                {"mid": mid},
            )

        self.db.commit()
        return len(ids)  # 등급 갱신을 요청한 회원 수