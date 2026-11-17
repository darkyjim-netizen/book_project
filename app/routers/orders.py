"""주문, 결제, 배송 API 라우터."""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core import config
from app.core.database import get_db
from app.core.exceptions import BusinessError
from app.core.security import (
    create_guest_order_token,
    get_current_member,
    get_current_member_optional,
    require_admin,
    verify_guest_order_token,
)
from app.models.member import Member
from app.models.enums import OrderStatus, PaymentMethod
from app.models.order import Order
from app.schemas.common import MessageResponse, PageMeta, PageResponse
from app.schemas.order import (
    InvoiceRegisterRequest,
    OrderCancelRequest,
    OrderCreateRequest,
    OrderCreateResponse,
    OrderResponse,
    PaymentConfirmRequest,
    PaymentResponse,
    ShipmentResponse,
    TrackingResponse,
)
from app.services.order_service import OrderService
from app.services.payment_service import PaymentService
from app.services.shipment_service import ShipmentService
from app.routers.cart import SESSION_COOKIE


# 이 라우터에 등록된 주소는 모두 /orders로 시작한다.
router = APIRouter(prefix="/orders", tags=["주문"])


@router.post("", response_model=OrderCreateResponse, summary="주문 생성")
def create_order(
    payload: OrderCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    # 로그인한 회원이면 회원 정보를 받고, 비회원이면 None을 받는다.
    member=Depends(get_current_member_optional),
):
    """장바구니 또는 요청 상품으로 주문을 생성한다."""

    service = OrderService(db)

    # 주문 처리는 서비스에 맡기고, 만들어진 주문을 API 응답 형식으로 변환한다.
    order = service.create_order(
        member, payload, cart_session_key=request.cookies.get(SESSION_COOKIE)
    )
    response = service.to_response(order)
    return OrderCreateResponse(
        **response.model_dump(),
        # 비회원에게만 이 주문 결제에 사용할 서명 토큰을 발급한다.
        guest_order_token=(
            create_guest_order_token(order.order_id)
            if member is None
            else None
        ),
    )


@router.get(
    "",
    response_model=PageResponse[OrderResponse],
    summary="내 주문 목록",
)
def list_orders(
    page: int = Query(1, ge=1),  # 조회할 페이지 번호. 1보다 작을 수 없다.
    size: int = Query(10, ge=1, le=50),  # 한 페이지에 표시할 주문 수
    status: Optional[str] = None,  # 특정 주문 상태만 조회할 때 사용
    date_from: Optional[datetime] = None,  # 주문 날짜 조회 시작
    date_to: Optional[datetime] = None,  # 주문 날짜 조회 끝
    member: Member = Depends(get_current_member),  # 로그인 회원만 조회할 수 있다.
    db: Session = Depends(get_db),
):
    """로그인 회원의 주문 목록을 페이지 단위로 조회한다."""

    service = OrderService(db)

    # 검색 조건에 맞는 주문 목록과 전체 건수를 가져온다.
    rows, total = service.list_orders(
        member,
        page,
        size,
        status,
        date_from,
        date_to,
    )

    # 주문 객체들을 응답 스키마로 바꾸고 페이지 정보를 함께 반환한다.
    return PageResponse[OrderResponse](
        items=[service.to_response(order) for order in rows],
        meta=PageMeta.build(page, size, total),
    )


@router.get("/stats", response_model=dict, summary="내 주문 통계")
def order_stats(
    member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    """마이페이지에 표시할 회원의 주문 상태별 통계를 반환한다."""

    return OrderService(db).member_order_stats(member.member_id)


@router.get("/lookup", response_model=OrderResponse, summary="비회원 주문 조회")
def lookup_order(
    order_no: str = Query(..., description="주문번호"),
    email: str = Query(..., description="주문 시 입력한 이메일"),
    db: Session = Depends(get_db),
):
    """주문번호와 주문자 이메일로 비회원 주문을 조회한다."""

    service = OrderService(db)

    # 주문번호만으로 조회하지 않고 이메일도 함께 확인한다.
    order = service.get_by_order_no(order_no, email)
    if order.member_id is not None:
        raise HTTPException(status_code=404, detail="비회원 주문을 찾을 수 없습니다.")
    return service.to_response(order)


# 주문서가 서버와 같은 결제 모드 및 배송비를 사용하도록 알려준다.
@router.get("/payment-mode", summary="주문 결제 설정")
def get_payment_mode(member=Depends(get_current_member_optional)):
    settings = config.settings
    # 비회원은 회원 등급이 없으므로 기본 무료배송 기준을 적용한다.
    free_shipping_limit = (
        member.grade.free_ship_limit
        if member is not None and member.grade
        else settings.FREE_SHIP_LIMIT
    )
    return {
        "mode": "mock" if settings.PG_MOCK_MODE else "toss",
        "shipping_fee": settings.DEFAULT_SHIP_FEE,
        "free_shipping_limit": free_shipping_limit,
    }


@router.get("/{order_id}", response_model=OrderResponse, summary="주문 상세")
def get_order(
    order_id: int,
    member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    """로그인 회원의 주문 상세 정보를 조회한다."""

    service = OrderService(db)

    # 서비스에서 주문이 있는지와 본인 주문인지 확인한 뒤 응답으로 바꾼다.
    order = service.get_order(order_id, member)
    return service.to_response(order)


# 본인 주문에 저장된 금액과 공개 키로 토스 결제창을 준비한다.
@router.get("/{order_id}/payment-ready", summary="토스 결제 준비")
def get_payment_ready(
    order_id: int,
    # 비회원은 주문 생성 응답의 토큰을 헤더로 전달한다.
    guest_order_token: Optional[str] = Header(None, alias="X-Guest-Order-Token"),
    member=Depends(get_current_member_optional),
    db: Session = Depends(get_db),
):
    if member is None:
        verify_guest_order_token(guest_order_token, order_id)

    order = OrderService(db).get_order(order_id, member)
    # 비회원 인증 토큰으로 회원 주문에 접근하지 못하게 확인한다.
    if member is None and order.member_id is not None:
        raise HTTPException(status_code=403, detail="해당 주문에 접근할 수 없습니다.")
    payment = PaymentService(db).get_payment(order_id)
    if order.status != OrderStatus.PENDING or payment.pg_tid:
        raise BusinessError("결제 대기 상태의 주문만 결제할 수 있습니다.")
    if payment.method not in (PaymentMethod.CARD, PaymentMethod.TRANSFER):
        raise BusinessError("토스 결제창에서는 카드·간편결제와 계좌이체를 지원합니다.")

    client_key = config.toss_client_key()
    if config.settings.PG_MOCK_MODE or not client_key or not config.toss_secret_key():
        raise BusinessError("토스페이먼츠 결제 설정을 확인해 주세요.", status_code=503)
    amount = int(payment.amount)
    if amount <= 0 or amount != payment.amount:
        raise BusinessError("토스 결제 금액은 1원 이상의 정수여야 합니다.")

    return {
        "client_key": client_key,
        "amount": amount,
        "order_id": order.order_no,
        "order_name": f"도서 주문 {order.order_no}",
        "customer_name": order.orderer_name,
        "success_url": "/shop.html?toss=success",
        "fail_url": "/shop.html?toss=fail",
    }


@router.post(
    "/{order_id}/pay",
    response_model=PaymentResponse,
    summary="결제 요청",
)
def pay_order(
    order_id: int,
    # 요청 JSON에 담긴 PG 추가 정보. 예: {"payment_key": "..."}
    extra: dict = Body(
        default={},
        description="카드명 등 PG 추가 파라미터",
    ),
    db: Session = Depends(get_db),
    # 비회원 주문 결제도 허용할 수 있도록 선택적 회원 인증을 사용한다.
    member=Depends(get_current_member_optional),
    # 비회원은 주문 생성 때 발급된 토큰으로 주문을 인증한다.
    guest_order_token: Optional[str] = Header(None, alias="X-Guest-Order-Token"),
):
    """주문에 대해 PG 결제를 요청한다."""

    # 요청자가 주문을 볼 수 있는지 먼저 확인한다.
    if member is None:
        verify_guest_order_token(guest_order_token, order_id)

    order = OrderService(db).get_order(order_id, member)
    if member is None and order.member_id is not None:
        raise HTTPException(status_code=403, detail="해당 주문에 접근할 수 없습니다.")

    # 결제 승인과 결제 DB 처리는 결제 서비스에 맡긴다.
    service = PaymentService(db)
    if not config.settings.PG_MOCK_MODE:
        # 토스에서 돌아온 주문번호와 금액을 서버에 저장된 값과 대조한다.
        current_payment = service.get_payment(order_id)
        if not isinstance(extra.get("payment_key"), str) or not extra["payment_key"]:
            raise BusinessError("토스 결제 승인에 필요한 결제 키가 없습니다.")
        if extra.get("order_no", order.order_no) != order.order_no or extra.get(
            "amount", current_payment.amount
        ) != current_payment.amount:
            raise BusinessError("토스 인증 결과가 주문번호 또는 결제 금액과 일치하지 않습니다.")
        extra = {"payment_key": extra["payment_key"]}
    payment = service.request_payment(order_id, extra)

    # DB 결제 객체를 API 응답 형식으로 변환한다.
    return PaymentResponse.model_validate(payment)


@router.post(
    "/payments/callback",
    response_model=PaymentResponse,
    summary="PG 결제 콜백",
)
def payment_callback(
    payload: PaymentConfirmRequest,
    db: Session = Depends(get_db),
):
    """PG사에서 보내는 결제 결과 통보를 처리한다."""

    # 토스 모드에서는 이전 PG 형식의 콜백으로 결제를 확정할 수 없다.
    if not config.settings.PG_MOCK_MODE:
        raise BusinessError("토스 결제는 주문 결제 승인 API를 사용해 주세요.", status_code=404)

    # 결제 성공·실패 결과를 결제 서비스에서 확인하고 DB에 반영한다.
    payment = PaymentService(db).confirm_callback(payload)
    return PaymentResponse.model_validate(payment)


@router.post("/{order_id}/cancel", response_model=OrderResponse, summary="주문 취소")
def cancel_order(
    order_id: int,
    payload: OrderCancelRequest,  # 취소 사유 코드와 상세 사유
    # 비회원은 주문 생성 때 받은 토큰으로 주문 취소 권한을 증명한다.
    guest_order_token: Optional[str] = Header(None, alias="X-Guest-Order-Token"),
    member=Depends(get_current_member_optional),
    db: Session = Depends(get_db),
):
    """주문을 취소하고 재고, 포인트, 쿠폰 등을 복원한다."""

    service = OrderService(db)
    if member is None:
        verify_guest_order_token(guest_order_token, order_id)

    order = service.get_order(order_id, member)
    if member is None and order.member_id is not None:
        raise HTTPException(status_code=403, detail="해당 주문에 접근할 수 없습니다.")
    # 결제창 실패로 취소할 때 이미 승인된 주문은 건드리지 않는다.
    if payload.reason_code == "PAYMENT_INCOMPLETE":
        order = db.get(Order, order_id, with_for_update=True)
        if order is not None and order.status != OrderStatus.PENDING:
            raise BusinessError("결제 대기 상태의 주문만 결제 실패로 취소할 수 있습니다.")

    # 취소 가능 여부를 확인하고 취소 처리를 수행한다.
    order = service.cancel_order(
        order_id,
        member,
        payload.reason_code,
        payload.reason_text,
    )
    return service.to_response(order)


@router.post("/{order_id}/confirm", response_model=OrderResponse, summary="구매 확정")
def confirm_order(
    order_id: int,
    member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    """회원이 구매를 확정하고 적립 포인트를 받는다."""

    service = OrderService(db)

    # 본인 주문인지 확인하고 구매 확정 처리를 한다.
    order = service.confirm_purchase(order_id, member)
    return service.to_response(order)


@router.post("/{order_id}/return", response_model=OrderResponse, summary="반품 접수")
def request_return(
    order_id: int,
    # 요청 JSON 예: {"reason_text": "상품이 파손되어 도착했습니다."}
    reason_text: Optional[str] = Body(None, embed=True),
    member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    """회원의 반품을 접수한다."""

    service = OrderService(db)

    # 배송 상태와 반품 가능 기간 등을 서비스에서 확인한다.
    order = service.request_return(order_id, member, reason_text)
    return service.to_response(order)


@router.get(
    "/{order_id}/shipment",
    response_model=ShipmentResponse,
    summary="배송 조회",
)
def get_shipment(
    order_id: int,
    member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    """주문의 배송 정보와 배송 추적 기록을 조회한다."""

    # 회원 본인의 주문인지 먼저 확인한다.
    OrderService(db).get_order(order_id, member)

    # 주문에 연결된 배송 정보를 찾는다.
    shipment = ShipmentService(db).get_shipment(order_id)

    # 배송 정보와 추적 기록을 API 응답 형식으로 구성한다.
    return ShipmentResponse(
        shipment_id=shipment.shipment_id,
        carrier_code=shipment.carrier_code,
        carrier_name=shipment.carrier_name,
        invoice_no=shipment.invoice_no,
        status=shipment.status.value,
        shipped_at=shipment.shipped_at,
        delivered_at=shipment.delivered_at,
        # 배송 추적 기록을 발생 시각 순서로 정렬한다.
        tracking=[
            TrackingResponse(
                status=tracking.status.value,
                location=tracking.location,
                description=tracking.description,
                occurred_at=tracking.occurred_at,
            )
            for tracking in sorted(
                shipment.tracking,
                key=lambda item: item.occurred_at,
            )
        ],
    )


@router.get(
    "/{order_id}/tracking-url",
    response_model=dict,
    summary="택배사 조회 URL",
)
def tracking_url(
    order_id: int,
    member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    """택배사 사이트에서 송장을 조회할 수 있는 URL을 반환한다."""

    # 회원 본인의 주문인지 확인한다.
    OrderService(db).get_order(order_id, member)

    service = ShipmentService(db)
    shipment = service.get_shipment(order_id)

    # 택배사 코드와 송장 번호로 택배사 조회 주소를 만든다.
    return {
        "carrier_name": shipment.carrier_name,
        "invoice_no": shipment.invoice_no,
        "url": service.tracking_url(
            shipment.carrier_code,
            shipment.invoice_no or "",
        ),
    }


# -----------------------------------------------------------------------------
# 관리자 배송 관리 API
# -----------------------------------------------------------------------------

# 이 라우터의 주소는 /admin/shipments로 시작한다.
admin_shipment_router = APIRouter(
    prefix="/admin/shipments",
    tags=["관리자-배송"],
)


@admin_shipment_router.post(
    "/{order_id}/invoice",
    response_model=ShipmentResponse,
    summary="송장 등록",
)
def register_invoice(
    order_id: int,
    payload: InvoiceRegisterRequest,
    # 관리자 권한이 없으면 요청을 허용하지 않는다.
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """주문에 송장을 등록하고 배송을 시작한다."""

    shipment = ShipmentService(db).register_invoice(
        order_id,
        payload.carrier_code,
        payload.carrier_name,
        payload.invoice_no,
    )

    # 등록된 배송 정보를 응답 형식으로 반환한다.
    return ShipmentResponse(
        shipment_id=shipment.shipment_id,
        carrier_code=shipment.carrier_code,
        carrier_name=shipment.carrier_name,
        invoice_no=shipment.invoice_no,
        status=shipment.status.value,
        shipped_at=shipment.shipped_at,
        delivered_at=shipment.delivered_at,
        tracking=[],
    )


@admin_shipment_router.post(
    "/bulk-invoice",
    response_model=MessageResponse,
    summary="송장 일괄 등록",
)
def bulk_invoice(
    # 요청 JSON 예: {"order_ids": [1, 2, 3]}
    order_ids: List[int] = Body(..., embed=True),
    # 요청 JSON에 carrier_code가 없으면 CJ대한통운을 사용한다.
    carrier_code: str = Body("CJ", embed=True),
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """여러 주문에 송장을 한 번에 등록한다."""

    count = ShipmentService(db).bulk_register_invoice(
        order_ids,
        carrier_code,
    )

    return MessageResponse(
        message=f"{count}건의 송장이 등록되었습니다."
    )


@admin_shipment_router.post(
    "/{order_id}/tracking",
    response_model=TrackingResponse,
    summary="배송 이력 추가",
)
def add_tracking(
    order_id: int,
    # 요청 JSON 예: {"status": "IN_TRANSIT", "location": "옥천 HUB"}
    status: str = Body(..., embed=True),
    location: Optional[str] = Body(None, embed=True),
    description: Optional[str] = Body(None, embed=True),
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """관리자가 배송 추적 이력을 직접 추가한다."""

    tracking = ShipmentService(db).add_tracking(
        order_id,
        status,
        location,
        description,
    )

    return TrackingResponse(
        status=tracking.status.value,
        location=tracking.location,
        description=tracking.description,
        occurred_at=tracking.occurred_at,
    )


@admin_shipment_router.post(
    "/{order_id}/simulate",
    response_model=List[dict],
    summary="배송 진행 시뮬레이션",
)
def simulate(
    order_id: int,
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """테스트용 배송 추적 기록을 순서대로 생성한다."""

    return ShipmentService(db).simulate_progress(order_id)


@admin_shipment_router.get(
    "/pending",
    response_model=List[dict],
    summary="발송 대기 목록",
)
def pending_shipments(
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """결제는 완료됐지만 송장이 아직 등록되지 않은 배송을 조회한다."""

    rows = ShipmentService(db).list_pending_shipments()

    # 관리자 화면에서 필요한 정보만 추려 목록으로 반환한다.
    return [
        {
            "shipment_id": shipment.shipment_id,
            "order_id": shipment.order_id,
            "order_no": (
                shipment.order.order_no
                if shipment.order
                else None
            ),
            "receiver": (
                shipment.order.receiver
                if shipment.order
                else None
            ),
            "created_at": shipment.created_at,
        }
        for shipment in rows
    ]


@admin_shipment_router.get(
    "/stats",
    response_model=dict,
    summary="배송 상태 통계",
)
def shipment_stats(
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """배송 상태별 건수를 반환한다."""

    return ShipmentService(db).shipment_stats()
