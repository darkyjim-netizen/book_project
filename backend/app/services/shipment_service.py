"""배송 서비스: 송장 등록, 배송 추적, 상태 동기화."""
import logging
import random
import string
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import BusinessError, NotFoundError
from app.models.enums import OrderStatus, ShipmentStatus
from app.models.order import Order, Shipment, ShipmentTracking

logger = logging.getLogger(__name__)


# 택배사 코드별 이름과 배송 조회 페이지 주소
# {no} 부분에는 실제 송장 번호가 들어간다.
CARRIERS = {
    "CJ": {
        "name": "CJ대한통운",
        "url": "https://trace.cjlogistics.com/next/tracking.html?wblNo={no}",
    },
    "HANJIN": {
        "name": "한진택배",
        "url": "https://www.hanjin.com/kor/CMS/DeliveryMgr/WaybillResult.do?wblnum={no}",
    },
    "LOTTE": {
        "name": "롯데택배",
        "url": "https://www.lotteglogis.com/home/reservation/tracking/linkView?InvNo={no}",
    },
    "POST": {
        "name": "우체국택배",
        "url": "https://service.epost.go.kr/trace.RetrieveRegiPrclDeliv.postal?sid1={no}",
    },
    "LOGEN": {
        "name": "로젠택배",
        "url": "https://www.ilogen.com/web/personal/trace/{no}",
    },
}


# 실제 택배사 조회 대신 데모에서 사용할 가상의 배송 진행 순서
# 각 항목은 (배송 상태, 위치, 설명, 발송 후 경과 시간)으로 구성된다.
TRACKING_SCENARIO = [
    (
        ShipmentStatus.PICKED,
        "물류센터",
        "상품이 집화 처리되었습니다.",
        0,
    ),
    (
        ShipmentStatus.IN_TRANSIT,
        "옥천 HUB",
        "상품이 간선 상차되었습니다.",
        6,
    ),
    (
        ShipmentStatus.IN_TRANSIT,
        "도착 지점",
        "상품이 배송지 지점에 도착했습니다.",
        18,
    ),
    (
        ShipmentStatus.OUT_FOR_DELIVERY,
        "배송 출발",
        "배송 기사가 배송을 시작했습니다.",
        24,
    ),
    (
        ShipmentStatus.DELIVERED,
        "배송지",
        "배송이 완료되었습니다.",
        30,
    ),
]


class ShipmentService:
    """송장과 배송 정보를 조회하고 변경하는 서비스."""

    def __init__(self, db: Session):
        # 서비스 메서드에서 사용할 DB 연결
        self.db = db

    def get_shipment(self, order_id: int) -> Shipment:
        """주문 번호로 배송 정보를 찾는다."""

        shipment = self.db.scalar(
            select(Shipment)
            # 배송 정보를 조회하면서 배송 추적 기록도 함께 불러온다.
            .options(selectinload(Shipment.tracking))
            .where(Shipment.order_id == order_id)
        )

        if shipment is None:
            raise NotFoundError("배송 정보를 찾을 수 없습니다.")

        return shipment

    @staticmethod
    def generate_invoice_no() -> str:
        """데모용 송장 번호 12자리를 임의로 만든다."""

        # 실제 택배사에서 발급한 송장 번호가 아니라 테스트용 번호다.
        return "".join(random.choices(string.digits, k=12))

    @staticmethod
    def tracking_url(
        carrier_code: str,
        invoice_no: str,
    ) -> Optional[str]:
        """택배사 코드와 송장 번호로 배송 조회 URL을 만든다."""

        carrier = CARRIERS.get(carrier_code)

        # 등록되지 않은 택배사이거나 송장 번호가 없으면 URL을 만들 수 없다.
        if not carrier or not invoice_no:
            return None

        # 택배사 URL의 {no} 자리에 송장 번호를 넣는다.
        return carrier["url"].format(no=invoice_no)

    # ------------------------------------------------------------------ 송장 등록
    def register_invoice(
        self,
        order_id: int,
        carrier_code: str,
        carrier_name: str,
        invoice_no: str,
    ) -> Shipment:
        """송장을 저장하고 주문과 배송 상태를 배송 중으로 바꾼다."""

        # 주문이 실제로 존재하는지 확인한다.
        order = self.db.get(Order, order_id)
        if order is None:
            raise NotFoundError("주문을 찾을 수 없습니다.")

        # 결제가 끝났거나 상품 준비 중인 주문만 발송할 수 있다.
        if order.status not in (
            OrderStatus.PAID,
            OrderStatus.PREPARING,
        ):
            raise BusinessError(
                "결제 완료 또는 상품 준비 중 상태에서만 송장을 등록할 수 있습니다."
            )

        # 주문에 연결된 배송 정보를 찾는다.
        shipment = self.get_shipment(order_id)

        # 택배사와 송장 정보를 배송 데이터에 저장한다.
        shipment.carrier_code = carrier_code

        # 택배사 이름이 전달되지 않으면 코드에 등록된 이름을 사용한다.
        # 등록되지 않은 택배사라면 택배사 코드를 이름 대신 저장한다.
        shipment.carrier_name = (
            carrier_name
            or CARRIERS.get(carrier_code, {}).get("name", carrier_code)
        )
        shipment.invoice_no = invoice_no

        # 송장이 등록되면 배송이 집화된 상태로 기록한다.
        shipment.status = ShipmentStatus.PICKED
        shipment.shipped_at = datetime.now(timezone.utc)

        # 첫 번째 배송 추적 기록을 만든다.
        self.db.add(
            ShipmentTracking(
                shipment_id=shipment.shipment_id,
                status=ShipmentStatus.PICKED,
                location="물류센터",
                description="상품이 집화 처리되었습니다.",
            )
        )

        # 주문과 주문 상품의 상태를 배송 중으로 변경한다.
        order.status = OrderStatus.SHIPPING
        for item in order.items:
            item.status = OrderStatus.SHIPPING

        # 변경 사항을 DB에 저장하고 최신 배송 정보를 다시 읽는다.
        self.db.commit()
        self.db.refresh(shipment)

        logger.info(
            "송장 등록: order=%s carrier=%s invoice=%s",
            order.order_no,
            carrier_code,
            invoice_no,
        )

        return shipment

    def bulk_register_invoice(
        self,
        order_ids: List[int],
        carrier_code: str = "CJ",
    ) -> int:
        """여러 주문의 송장을 한 번에 등록하고 성공 건수를 반환한다."""

        count = 0

        # 택배사 코드에 맞는 이름을 가져온다.
        carrier_name = CARRIERS.get(carrier_code, {}).get(
            "name",
            carrier_code,
        )

        for order_id in order_ids:
            try:
                # 각 주문에 테스트용 송장 번호를 만들어 등록한다.
                self.register_invoice(
                    order_id,
                    carrier_code,
                    carrier_name,
                    self.generate_invoice_no(),
                )
                count += 1

            except (BusinessError, NotFoundError):
                # 처리할 수 없는 주문은 건너뛰고 나머지 주문을 계속 처리한다.
                continue

        return count

    # ------------------------------------------------------------------ 배송 추적
    def add_tracking(
        self,
        order_id: int,
        status: str,
        location: Optional[str],
        description: Optional[str],
    ) -> ShipmentTracking:
        """배송 진행 기록을 추가하고 현재 배송 상태를 갱신한다."""

        shipment = self.get_shipment(order_id)

        # 전달받은 문자열 상태를 ShipmentStatus 값으로 변환한다.
        new_status = ShipmentStatus(status)

        # 새 배송 추적 기록을 만든다.
        tracking = ShipmentTracking(
            shipment_id=shipment.shipment_id,
            status=new_status,
            location=location,
            description=description,
        )
        self.db.add(tracking)

        # 배송 정보의 현재 상태도 새 추적 상태로 맞춘다.
        shipment.status = new_status

        # 배송 완료 상태라면 배송 정보와 주문 정보도 완료로 바꾼다.
        if new_status == ShipmentStatus.DELIVERED:
            now = datetime.now(timezone.utc)
            shipment.delivered_at = now

            order = self.db.get(Order, order_id)

            # 주문이 아직 배송 중일 때만 주문 상태를 배송 완료로 바꾼다.
            if order and order.status == OrderStatus.SHIPPING:
                order.status = OrderStatus.DELIVERED
                order.delivered_at = now

                # 주문에 담긴 상품들의 상태도 배송 완료로 변경한다.
                for item in order.items:
                    item.status = OrderStatus.DELIVERED

        self.db.commit()
        self.db.refresh(tracking)

        return tracking

    def simulate_progress(self, order_id: int) -> List[Dict]:
        """데모용 배송 진행 기록을 한 번에 만들어 반환한다."""

        shipment = self.get_shipment(order_id)

        # 배송 추적 기록을 만들려면 먼저 송장이 등록되어 있어야 한다.
        if not shipment.invoice_no:
            raise BusinessError("송장이 등록되지 않았습니다.")

        # 발송 시각을 기준으로 각 배송 단계의 시간을 계산한다.
        # 발송 시각이 없다면 현재 시각을 기준으로 삼는다.
        base = shipment.shipped_at or datetime.now(timezone.utc)

        # 이 함수를 다시 실행해도 기록이 중복되지 않도록 기존 추적 기록을 삭제한다.
        self.db.query(ShipmentTracking).filter(
            ShipmentTracking.shipment_id == shipment.shipment_id
        ).delete(synchronize_session=False)

        result = []

        # 시나리오의 단계마다 배송 추적 기록을 만든다.
        for status, location, desc, hours in TRACKING_SCENARIO:
            occurred = base + timedelta(hours=hours)

            self.db.add(
                ShipmentTracking(
                    shipment_id=shipment.shipment_id,
                    status=status,
                    location=location,
                    description=desc,
                    occurred_at=occurred,
                )
            )

            # API 응답에 사용할 추적 기록도 목록에 담는다.
            result.append(
                {
                    "status": status.value,
                    "location": location,
                    "description": desc,
                    "occurred_at": occurred,
                }
            )

        # 시나리오의 마지막 단계가 배송 완료이므로 배송 정보를 완료 상태로 바꾼다.
        shipment.status = ShipmentStatus.DELIVERED
        shipment.delivered_at = base + timedelta(hours=30)

        order = self.db.get(Order, order_id)

        # 주문이 배송 중인 경우 주문과 주문 상품 상태도 배송 완료로 바꾼다.
        if order and order.status == OrderStatus.SHIPPING:
            order.status = OrderStatus.DELIVERED
            order.delivered_at = shipment.delivered_at

            for item in order.items:
                item.status = OrderStatus.DELIVERED

        self.db.commit()

        return result

    def list_pending_shipments(
        self,
        limit: int = 100,
    ) -> List[Shipment]:
        """결제는 됐지만 아직 송장이 등록되지 않은 배송을 조회한다."""

        return list(
            self.db.scalars(
                select(Shipment)
                # 배송 정보를 주문과 연결해 주문 상태도 함께 조건으로 확인한다.
                .join(Order, Order.order_id == Shipment.order_id)
                .where(
                    Shipment.invoice_no.is_(None),
                    Order.status.in_(
                        [
                            OrderStatus.PAID,
                            OrderStatus.PREPARING,
                        ]
                    ),
                )
                # 오래 기다린 배송 건부터 먼저 보여준다.
                .order_by(Shipment.created_at.asc())
                .limit(limit)
            ).unique()
        )

    def shipment_stats(self) -> Dict[str, int]:
        """현재 배송 상태별 배송 건수를 집계한다."""

        from sqlalchemy import func

        # 각 배송 상태별로 행의 개수를 센다.
        rows = self.db.execute(
            select(
                Shipment.status,
                func.count(),
            ).group_by(Shipment.status)
        ).all()

        # Enum 상태값을 문자열로 바꾸어 {상태: 건수} 형태로 반환한다.
        return {
            row[0].value: row[1]
            for row in rows
        }