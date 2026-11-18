"""
결제(Payment) API 라우터 (책 6.5절)
토스페이먼츠 결제 요청 준비, 승인 처리, 취소, 콜백 처리를 담당합니다.
"""
from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth.auth_dependencies import current_member
from app.core import config
from app.core.api_errors import api_error
from app.crud.order_crud import get_order_by_id
from app.database import get_db
from app.models.user_model import Member
from app.services.payment_service import TossPaymentService


router = APIRouter(prefix="/api/payments", tags=["결제"])
# 서버를 어느 폴더에서 실행하든 프로젝트 루트의 templates 폴더를 찾습니다.
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[2] / "templates")


# ── 결제 준비 데이터 조회 (결제창 초기화용)
@router.get("/toss/{order_id}/ready", summary="토스 결제창 초기화 데이터")
async def get_payment_ready(order_id: int, member: Member = Depends(current_member),
                            db: Session = Depends(get_db)):
    """
    프론트엔드에서 토스 결제창을 열기 위한 데이터를 반환합니다.
    클라이언트 키, 주문 정보, 금액(서버 계산값)을 포함합니다.
    """
    order = get_order_by_id(db, order_id, member.id)
    if order is None:
        raise api_error(404, "ORDER_NOT_FOUND", "주문을 찾을 수 없습니다.")
    return TossPaymentService(db).get_payment_ready_data(order)


# ── 결제 승인 처리 (결제 성공 콜백)
@router.get("/toss/success", summary="토스 결제 성공 콜백")
async def toss_payment_success(
    paymentKey: str = Query(..., description="PG사 결제 키"),
    orderId: str = Query(..., description="주문번호"),
    amount: int = Query(..., description="결제 금액"),
    db: Session = Depends(get_db),
):
    """
    토스 결제 성공 후 리디렉션되는 콜백 엔드포인트입니다.
    이 엔드포인트에서 서버 사이드 결제 최종 승인을 처리합니다.
    """
    try:
        result = await TossPaymentService(db).confirm_payment(
            payment_key=paymentKey, order_number=orderId, amount=amount)
    except HTTPException as exc:
        # 결제 실패 페이지로 리디렉션 (한글 메시지가 깨지지 않도록 URL 인코딩)
        detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
        query = urlencode({"code": detail.get("code", "UNKNOWN"),
                           "message": detail.get("message", "결제가 실패했습니다."), "orderId": orderId})
        return RedirectResponse(url=f"{config.payment_fail_url()}?{query}", status_code=303)

    # 결제 완료 페이지(프런트엔드)로 리디렉션
    return RedirectResponse(url=f"{config.frontend_url()}/orders/{result['order'].id}/complete", status_code=303)


# ── 결제 실패 처리
@router.get("/toss/fail", response_class=HTMLResponse, summary="토스 결제 실패 콜백")
async def toss_payment_fail(
    request: Request,
    code: str = Query(default="UNKNOWN"),
    message: str = Query(default="결제가 실패했습니다."),
    orderId: str = Query(default=""),
):
    """결제 실패 페이지를 반환합니다."""
    return templates.TemplateResponse(request, "payments/fail.html", {
        "error_code": code,
        "error_message": message,
        "order_id": orderId,
        "frontend_url": config.frontend_url(),
    })


# ── 결제 취소 API
@router.post("/{order_id}/cancel", summary="결제 취소")
async def cancel_payment(
    order_id: int,
    cancel_reason: str = Query(default="고객 요청", min_length=1, max_length=200),
    member: Member = Depends(current_member),
    db: Session = Depends(get_db),
):
    """
    결제를 전액 취소합니다.
    결제 전 취소는 DB 상태 변경만, 결제 후 취소는 PG사 취소 API도 호출합니다.
    """
    order = get_order_by_id(db, order_id, member.id)
    if order is None:
        raise api_error(404, "ORDER_NOT_FOUND", "주문을 찾을 수 없습니다.")
    return await TossPaymentService(db).cancel_payment(order=order, cancel_reason=cancel_reason)
