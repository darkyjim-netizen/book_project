"""관리자 API 라우터: 대시보드, 도서, 회원, 주문을 관리한다."""
from datetime import date, timedelta
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, Query, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_admin, require_superadmin
from app.models.member import Member
from app.models.enums import OrderStatus
from app.schemas.ai import DashboardKpi, DashboardResponse
from app.schemas.book import (
    BookCreateRequest,
    BookDetailResponse,
    BookListItem,
    BookSearchParams,
    BookUpdateRequest,
    StockUpdateRequest,
)
from app.schemas.common import MessageResponse, PageMeta, PageResponse
from app.schemas.member import MemberResponse
from app.schemas.order import OrderResponse, OrderStatusUpdateRequest
from app.services.book_service import BookService
from app.services.member_service import MemberService
from app.services.order_service import OrderService


# 관리자 API 주소는 모두 /admin으로 시작한다.
router = APIRouter(prefix="/admin", tags=["관리자"])


@router.get("/dashboard/overview", summary="운영 대시보드 집계")
def dashboard_overview(_admin: Member = Depends(require_admin), db: Session = Depends(get_db)):
    """한국 시간 기준 일별 주문과 결제 완료 주문의 인구통계를 집계한다."""
    totals = db.execute(text("""
        SELECT (SELECT COALESCE(SUM(amount - COALESCE(cancelled_amount, 0)), 0)
                FROM shop.payments WHERE status IN ('PAID', 'PARTIAL_CANCELLED')) AS total_sales,
               (SELECT COUNT(*) FROM shop.members) AS member_count,
               (SELECT COUNT(*) FROM shop.orders) AS order_count,
               (SELECT COUNT(*) FROM shop.orders WHERE status = 'PAID') AS paid_orders,
               (SELECT COUNT(*) FROM shop.books WHERE status = 'SALE' AND stock_qty > 0 AND stock_qty <= safety_stock) AS low_stock_books,
               (SELECT COUNT(*) FROM shop.books WHERE status IN ('SALE', 'SOLDOUT') AND stock_qty <= 0) AS out_of_stock_books
    """)).mappings().one()
    daily = db.execute(text("""
        SELECT (ordered_at AT TIME ZONE 'Asia/Seoul')::date AS day, COUNT(*) AS count
        FROM shop.orders
        WHERE ordered_at >= ((CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul')::date - 6)::timestamp AT TIME ZONE 'Asia/Seoul'
        GROUP BY 1 ORDER BY 1
    """)).mappings().all()
    age = db.execute(text("""
        SELECT CASE WHEN m.birth_date IS NULL OR m.birth_date > (o.ordered_at AT TIME ZONE 'Asia/Seoul')::date THEN '미상'
                    WHEN EXTRACT(YEAR FROM age((o.ordered_at AT TIME ZONE 'Asia/Seoul')::date, m.birth_date)) < 20 THEN '10대 이하'
                    WHEN EXTRACT(YEAR FROM age((o.ordered_at AT TIME ZONE 'Asia/Seoul')::date, m.birth_date)) >= 60 THEN '60대 이상'
                    ELSE (FLOOR(EXTRACT(YEAR FROM age((o.ordered_at AT TIME ZONE 'Asia/Seoul')::date, m.birth_date)) / 10) * 10)::int::text || '대' END AS label,
               COUNT(*) AS count
        FROM shop.orders o LEFT JOIN shop.members m ON m.member_id = o.member_id
        WHERE o.status IN ('PAID', 'PREPARING', 'SHIPPING', 'DELIVERED', 'CONFIRMED')
        GROUP BY 1 ORDER BY 1
    """)).mappings().all()
    region = db.execute(text("""
        SELECT COALESCE(NULLIF(split_part(trim(address1), ' ', 1), ''), '미상') AS label, COUNT(*) AS count
        FROM shop.orders WHERE status IN ('PAID', 'PREPARING', 'SHIPPING', 'DELIVERED', 'CONFIRMED')
        GROUP BY 1 ORDER BY count DESC, label
    """)).mappings().all()
    return {"total_sales": int(totals["total_sales"]), "member_count": totals["member_count"],
            "order_count": totals["order_count"], "paid_orders": totals["paid_orders"],
            "low_stock_books": totals["low_stock_books"], "out_of_stock_books": totals["out_of_stock_books"], "daily_orders": [dict(row) for row in daily],
            "age_groups": [dict(row) for row in age], "regions": [dict(row) for row in region]}


# =============================================================================
# 관리자 대시보드
# =============================================================================
@router.get("/purchase-demographics", summary="연령대·배송지별 결제 주문 집계")
def purchase_demographics(
    days: int = Query(90, ge=7, le=365),
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """개인 정보 없이 결제 주문을 연령대 및 배송 주소 첫 단어별로 집계한다."""
    counts = db.execute(
        text(
            """
            WITH purchases AS (
                SELECT CASE
                           WHEN m.birth_date IS NULL OR m.birth_date > o.ordered_at::date THEN '미상'
                           ELSE (EXTRACT(YEAR FROM age(o.ordered_at::date, m.birth_date))::int / 10 * 10)::text || '대'
                       END AS age_group,
                       COALESCE(NULLIF(split_part(btrim(o.address1), ' ', 1), ''), '미상') AS region
                FROM shop.orders o
                LEFT JOIN shop.members m ON m.member_id = o.member_id
                WHERE o.paid_at >= now() - make_interval(days => :days)
                  AND o.status IN ('PAID', 'PREPARING', 'SHIPPING', 'DELIVERED', 'CONFIRMED')
            )
            SELECT 'age_groups' AS kind, age_group AS label, COUNT(*) AS order_count
            FROM purchases GROUP BY age_group
            UNION ALL
            SELECT 'regions', region, COUNT(*)
            FROM purchases GROUP BY region
            ORDER BY kind, order_count DESC, label
            """
        ),
        {"days": days},
    ).mappings()
    result = {"age_groups": [], "regions": []}
    for row in counts:
        result[row["kind"]].append({"label": row["label"], "order_count": row["order_count"]})
    return result


@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    summary="관리자 대시보드",
)
def dashboard(
    _admin: Member = Depends(require_admin),  # 관리자만 이용할 수 있다.
    db: Session = Depends(get_db),
):
    """오늘의 주요 지표, 매출 추이, 베스트셀러, AI 분석 결과를 반환한다."""

    # 대시보드에서만 필요한 AI 분석 기능을 요청이 왔을 때 불러온다.
    from app.ai.customer_analytics import ChurnPredictor
    from app.ai.sales_analytics import SalesAnalytics, SalesForecaster

    # 오늘 주문, 매출, 회원, 리뷰 등의 요약 정보를 DB 뷰에서 가져온다.
    kpi_row = (
        db.execute(
            text("SELECT * FROM shop.v_dashboard_today")
        )
        .mappings()
        .first()
        or {}
    )

    # 어제의 매출과 주문 건수를 조회한다.
    # 취소된 주문은 어제 매출 합계에서 제외한다.
    change = (
        db.execute(
            text(
                """
                SELECT
                  COALESCE(
                    (
                        SELECT SUM(total_amount)
                        FROM shop.orders
                        WHERE ordered_at::date = CURRENT_DATE - 1
                          AND status <> 'CANCELLED'
                    ),
                    0
                  )::float AS yday_sales,
                  COALESCE(
                    (
                        SELECT COUNT(*)
                        FROM shop.orders
                        WHERE ordered_at::date = CURRENT_DATE - 1
                    ),
                    0
                  )::int AS yday_orders
                """
            )
        )
        .mappings()
        .first()
        or {}
    )

    # DB 결과가 비어 있거나 값이 NULL이면 0으로 처리한다.
    today_sales = float(kpi_row.get("today_sales") or 0)
    today_orders = int(kpi_row.get("today_orders") or 0)
    yday_sales = float(change.get("yday_sales") or 0)
    yday_orders = int(change.get("yday_orders") or 0)

    # 화면에 표시할 KPI 응답 객체를 만든다.
    kpi = DashboardKpi(
        today_orders=today_orders,
        today_sales=today_sales,
        today_members=int(kpi_row.get("today_members") or 0),
        today_reviews=int(kpi_row.get("today_reviews") or 0),
        waiting_qna=int(kpi_row.get("waiting_qna") or 0),
        open_chats=int(kpi_row.get("open_chats") or 0),
        low_stock_books=int(kpi_row.get("low_stock_books") or 0),

        # 어제 값이 0이면 나눗셈을 할 수 없으므로 증감률을 0으로 둔다.
        sales_change_rate=(
            round((today_sales - yday_sales) / yday_sales * 100, 2)
            if yday_sales
            else 0.0
        ),
        order_change_rate=(
            round((today_orders - yday_orders) / yday_orders * 100, 2)
            if yday_orders
            else 0.0
        ),
    )

    # 최근 주문 10건을 대시보드에 필요한 항목만 골라 가져온다.
    recent_orders = db.execute(
        text(
            """
            SELECT o.order_id, o.order_no, o.orderer_name,
                   o.total_amount::float, o.status::text, o.ordered_at
            FROM shop.orders o
            ORDER BY o.ordered_at DESC
            LIMIT 10
            """
        )
    ).mappings().all()

    # 오늘을 기준으로 최근 30일의 매출 추이와 베스트셀러를 구한다.
    analytics = SalesAnalytics(db)
    today = date.today()
    start_date = today - timedelta(days=29)

    sales_trend = analytics.daily_series(start_date, today)
    best_sellers = analytics.best_sellers(start_date, today, 10)
    category_sales = analytics.category_sales(start_date, today, 8)

    # 리뷰 감성분석 결과를 긍정·중립·부정 등 라벨별로 집계한다.
    sentiment = db.execute(
        text(
            """
            SELECT label::text, COUNT(*)::int
            FROM ai.review_sentiments
            GROUP BY label
            """
        )
    ).all()

    # 고객 이탈 위험도를 분석해 위험 등급별 인원수를 가져온다.
    churn = ChurnPredictor(db).risk_summary()

    # 대시보드에서 사용할 데이터를 하나의 응답 객체로 묶는다.
    return DashboardResponse(
        kpi=kpi,
        recent_orders=[dict(row) for row in recent_orders],
        sales_trend=sales_trend,
        best_sellers=best_sellers,
        category_sales=category_sales,
        churn_high_risk=churn.get("HIGH", 0),
        sentiment_ratio={
            row[0]: int(row[1])
            for row in sentiment
        },
        forecast_next_7d=SalesForecaster(db).next_days_total(7),
    )


@router.get(
    "/dashboard/alerts",
    response_model=List[dict],
    summary="운영 알림",
)
def alerts(
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """재고 부족, 미답변 문의 등 처리할 업무가 있는 항목을 반환한다."""

    # 여러 테이블의 대기 업무 수를 한 번의 SQL로 조회한다.
    rows = db.execute(
        text(
            """
            SELECT
                'LOW_STOCK' AS type,
                COUNT(*)::int AS count,
                '안전 재고 이하 도서' AS label
            FROM shop.books
            WHERE status = 'SALE'
              AND stock_qty <= safety_stock

            UNION ALL

            SELECT
                'WAITING_QNA',
                COUNT(*)::int,
                '미답변 문의'
            FROM shop.qna_questions
            WHERE status = 'WAITING'

            UNION ALL

            SELECT
                'OPEN_CHAT',
                COUNT(*)::int,
                '대기 중 상담'
            FROM shop.chat_rooms
            WHERE status = 'OPEN'

            UNION ALL

            SELECT
                'PENDING_SHIP',
                COUNT(*)::int,
                '발송 대기 주문'
            FROM shop.orders
            WHERE status IN ('PAID', 'PREPARING')

            UNION ALL

            SELECT
                'RETURN_REQ',
                COUNT(*)::int,
                '반품/교환 접수'
            FROM shop.orders
            WHERE status IN ('RETURN_REQ', 'EXCHANGE_REQ')
            """
        )
    ).mappings().all()

    # 처리할 건수가 0인 알림은 목록에서 제외한다.
    return [
        dict(row)
        for row in rows
        if int(row["count"]) > 0
    ]


# =============================================================================
# 도서 관리
# =============================================================================
@router.get(
    "/books",
    response_model=PageResponse[BookListItem],
    summary="도서 목록(관리자)",
)
def admin_list_books(
    keyword: Optional[str] = None,  # 제목 등으로 검색할 단어
    category_id: Optional[int] = None,  # 특정 카테고리만 조회할 때 사용
    page: int = Query(1, ge=1),  # 페이지 번호
    size: int = Query(20, ge=1, le=100),  # 페이지당 도서 수
    sort: str = "recent",  # 정렬 방법
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """관리자용 도서 목록을 조건에 맞춰 조회한다."""

    # 검색 조건을 하나의 객체로 묶어 서비스에 전달한다.
    params = BookSearchParams(
        keyword=keyword,
        category_id=category_id,
        page=page,
        size=size,
        sort=sort,
    )

    items, total = BookService(db).search(params)

    # 검색 결과와 전체 건수를 페이지 응답 형식으로 반환한다.
    return PageResponse[BookListItem](
        items=items,
        meta=PageMeta.build(page, size, total),
    )


@router.post(
    "/books",
    response_model=BookDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="도서 등록",
)
def create_book(
    payload: BookCreateRequest,  # 새 도서 정보
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """새 도서를 등록하고 상세 정보를 반환한다."""

    service = BookService(db)
    book = service.create_book(payload)

    # 등록 후 DB에서 다시 조회해 상세 응답 형식으로 바꾼다.
    return service.to_detail(service.get_book(book.book_id))


@router.put(
    "/books/{book_id}",
    response_model=BookDetailResponse,
    summary="도서 수정",
)
def update_book(
    book_id: int,  # 수정할 도서 번호
    payload: BookUpdateRequest,  # 바꿀 도서 정보
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """도서 정보를 수정하고 수정된 상세 정보를 반환한다."""

    service = BookService(db)
    service.update_book(book_id, payload)

    return service.to_detail(service.get_book(book_id))


@router.delete(
    "/books/{book_id}",
    response_model=MessageResponse,
    summary="도서 삭제",
)
def delete_book(
    book_id: int,
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """도서를 논리 삭제한다."""

    # 논리 삭제는 DB 행을 완전히 지우는 대신 삭제 상태로 표시하는 방식이다.
    BookService(db).delete_book(book_id)
    return MessageResponse(message="도서가 삭제되었습니다.")


@router.post(
    "/books/{book_id}/stock",
    response_model=BookListItem,
    summary="재고 조정",
)
def adjust_stock(
    book_id: int,
    payload: StockUpdateRequest,  # 증감 수량과 조정 사유
    admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """재고를 조정하고 변동 이력을 남긴다."""

    service = BookService(db)

    # 관리자 번호도 전달해 누가 재고를 변경했는지 기록한다.
    book = service.adjust_stock(
        book_id,
        payload.change_qty,
        payload.reason,
        admin.member_id,
    )

    return service.to_list_item(book)


@router.get(
    "/books/low-stock",
    response_model=List[BookListItem],
    summary="재고 부족 도서",
)
def low_stock(
    limit: int = Query(50, ge=1, le=200),  # 최대 조회 건수
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """안전 재고 이하인 도서 목록을 반환한다."""

    return BookService(db).list_low_stock(limit)


@router.get(
    "/books/{book_id}/stock-history",
    response_model=List[dict],
    summary="재고 변동 이력",
)
def stock_history(
    book_id: int,  # 이력을 볼 도서 번호
    limit: int = Query(50, ge=1, le=200),
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """도서의 최근 재고 변동 이력을 조회한다."""

    rows = db.execute(
        text(
            """
            SELECT history_id, change_qty, after_qty, reason, ref_id, created_at
            FROM log.stock_histories
            WHERE book_id = :bid
            ORDER BY created_at DESC
            LIMIT :lim
            """
        ),
        # SQL에 값을 직접 붙이지 않고 매개변수로 전달한다.
        {"bid": book_id, "lim": limit},
    ).mappings().all()

    return [dict(row) for row in rows]


# =============================================================================
# 주문 관리
# =============================================================================
@router.get(
    "/orders",
    response_model=PageResponse[OrderResponse],
    summary="주문 목록(관리자)",
)
def admin_list_orders(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    keyword: Optional[str] = None,
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """관리자가 전체 주문을 검색하고 페이지 단위로 조회한다."""

    service = OrderService(db)
    rows, total = service.list_all_orders(
        page,
        size,
        status_filter,
        keyword,
    )

    return PageResponse[OrderResponse](
        items=[
            service.to_response(order)
            for order in rows
        ],
        meta=PageMeta.build(page, size, total),
    )


@router.get(
    "/orders/claims",
    response_model=PageResponse[OrderResponse],
    summary="취소·반품·교환 목록(관리자)",
)
def admin_list_claims(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status_filter: Optional[OrderStatus] = Query(None, alias="status"),
    keyword: Optional[str] = None,
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    service = OrderService(db)
    rows, total = service.list_all_orders(
        page, size, status_filter.value if status_filter else None, keyword,
        claims_only=True,
    )
    return PageResponse[OrderResponse](
        items=[service.to_response(order) for order in rows],
        meta=PageMeta.build(page, size, total),
    )


@router.get(
    "/orders/{order_id}",
    response_model=OrderResponse,
    summary="주문 상세(관리자)",
)
def admin_get_order(
    order_id: int,
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """관리자가 주문 한 건의 상세 정보를 조회한다."""

    service = OrderService(db)
    order = service.get_order(order_id)

    return service.to_response(order)


@router.put(
    "/orders/{order_id}/status",
    response_model=OrderResponse,
    summary="주문 상태 변경",
)
def change_order_status(
    order_id: int,
    payload: OrderStatusUpdateRequest,  # 변경할 상태와 메모
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """관리자가 허용된 규칙에 따라 주문 상태를 변경한다."""

    service = OrderService(db)
    order = service.change_status(
        order_id,
        payload.status,
        payload.memo,
    )

    return service.to_response(order)


@router.post(
    "/orders/{order_id}/cancel",
    response_model=OrderResponse,
    summary="주문 강제 취소",
)
def admin_cancel_order(
    order_id: int,
    # 요청 JSON 예: {"reason_text": "고객 요청"}
    reason_text: Optional[str] = Body(None, embed=True),
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """관리자가 주문을 취소한다."""

    service = OrderService(db)

    from datetime import datetime, timezone
    from app.core.exceptions import BusinessError
    from app.models.enums import PaymentStatus
    from app.models.order import Refund
    from app.services.payment_service import PaymentService
    order = service.get_order(order_id)
    if not order.is_cancelable:
        raise BusinessError('현재 주문 상태에서는 취소할 수 없습니다.')
    payment = order.main_payment
    if payment and payment.status in (PaymentStatus.PAID, PaymentStatus.PARTIAL_CANCELLED):
        remaining = float(payment.amount) - float(payment.cancelled_amount or 0)
        if remaining > 0:
            PaymentService(db).cancel_payment(order_id, remaining, reason_text or '관리자 주문 취소')
            db.add(Refund(order_id=order_id, payment_id=payment.payment_id,
                          refund_amount=remaining, point_restore=order.point_used,
                          reason_code='ADMIN_CANCEL', reason_text=reason_text,
                          completed_at=datetime.now(timezone.utc)))

    # 회원이 직접 취소하는 것이 아니므로 member에는 None을 전달한다.
    order = service.cancel_order(
        order_id,
        None,
        "ADMIN_CANCEL",
        reason_text,
    )

    return service.to_response(order)


@router.post(
    "/orders/{order_id}/refund",
    response_model=dict,
    summary="결제 환불",
)
def refund_order(
    order_id: int,
    # 값이 없으면 결제 서비스가 남은 금액 전체를 취소하도록 처리한다.
    amount: Optional[float] = Body(None, embed=True, gt=0),
    reason: str = Body("관리자 환불", embed=True),
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """관리자가 결제를 전체 또는 일부 환불한다."""

    # 결제 서비스는 이 API에서만 사용하므로 여기서 불러온다.
    from app.services.payment_service import PaymentService

    payment = PaymentService(db).cancel_payment(
        order_id,
        amount,
        reason,
    )

    # 환불 결과 중 화면에 필요한 값만 반환한다.
    return {
        "payment_id": payment.payment_id,
        "status": payment.status.value,
        "cancelled_amount": float(payment.cancelled_amount),
    }


# =============================================================================
# 회원 관리
# =============================================================================
@router.get(
    "/members",
    response_model=PageResponse[MemberResponse],
    summary="회원 목록",
)
def admin_list_members(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    grade_id: Optional[int] = None,
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """검색 조건에 맞는 회원 목록을 조회한다."""

    rows, total = MemberService(db).list_members(
        page,
        size,
        keyword,
        status_filter,
        grade_id,
    )

    return PageResponse[MemberResponse](
        items=[
            MemberResponse.model_validate(member)
            for member in rows
        ],
        meta=PageMeta.build(page, size, total),
    )


@router.get(
    "/members/{member_id}",
    response_model=dict,
    summary="회원 상세",
)
def admin_get_member(
    member_id: int,
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """회원 정보와 주문 통계, 고객 분석 정보를 반환한다."""

    service = MemberService(db)
    member = service.get_member(member_id)

    # 해당 회원의 주문 요약 통계를 가져온다.
    order_stats = OrderService(db).member_order_stats(member_id)

    # AI 분석 테이블에 회원의 세그먼트 정보가 있는지 조회한다.
    segment = db.execute(
        text(
            """
            SELECT rfm_segment, r_score, f_score, m_score,
                   cluster_label, ltv_estimate::float,
                   recency_days, frequency, monetary::float
            FROM ai.customer_segments
            WHERE member_id = :mid
            """
        ),
        {"mid": member_id},
    ).mappings().first()

    # 해당 회원의 이탈 위험도 예측 결과를 조회한다.
    churn = db.execute(
        text(
            """
            SELECT churn_probability::float, risk_level,
                   top_features, predicted_at
            FROM ai.churn_predictions
            WHERE member_id = :mid
            """
        ),
        {"mid": member_id},
    ).mappings().first()

    # 회원 기본 정보와 분석 결과를 하나의 응답으로 묶는다.
    return {
        "member": MemberResponse.model_validate(member).model_dump(),
        "order_stats": order_stats,
        "segment": dict(segment) if segment else None,
        "churn": dict(churn) if churn else None,
    }


@router.put(
    "/members/{member_id}/status",
    response_model=MemberResponse,
    summary="회원 상태 변경",
)
def change_member_status(
    member_id: int,
    # 요청 JSON 예: {"status": "ACTIVE"} 또는 {"status": "SUSPENDED"}
    new_status: str = Body(..., embed=True, alias="status"),
    _admin: Member = Depends(require_superadmin),  # 최고 관리자만 변경 가능
    db: Session = Depends(get_db),
):
    """회원을 정지하거나 다시 이용할 수 있게 변경한다."""

    member = MemberService(db).change_status(member_id, new_status)
    return MemberResponse.model_validate(member)


@router.post(
    "/members/{member_id}/points",
    response_model=MemberResponse,
    summary="포인트 수동 조정",
)
def adjust_point(
    member_id: int,
    amount: int = Body(..., embed=True),  # 양수는 적립, 음수는 차감
    memo: str = Body("관리자 조정", embed=True),  # 조정 사유
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """관리자가 회원 포인트를 증감한다."""

    member = MemberService(db).adjust_point(
        member_id,
        amount,
        memo,
    )
    return MemberResponse.model_validate(member)


# =============================================================================
# 운영 배치 작업
# =============================================================================
@router.post(
    "/batch/{job_name}",
    response_model=dict,
    summary="운영 배치 실행",
)
def run_batch(
    job_name: str,  # 실행할 배치 작업 이름
    _admin: Member = Depends(require_superadmin),  # 최고 관리자만 실행 가능
    db: Session = Depends(get_db),
):
    """선택한 운영 배치 작업을 수동으로 실행한다.

    사용할 수 있는 job_name:
    auto_confirm, expire_vbank, expire_points,
    mark_dormant, refresh_grades, best_reviews
    """

    from app.core.exceptions import BusinessError
    from app.services.payment_service import PaymentService
    from app.services.review_service import ReviewService

    # 작업 이름과 실제 실행 함수를 연결한다.
    # lambda를 사용하면 선택된 작업만 나중에 실행할 수 있다.
    jobs = {
        "auto_confirm": lambda: OrderService(db).auto_confirm_delivered(),
        "expire_vbank": lambda: PaymentService(db).expire_unpaid_vbank(),
        "expire_points": lambda: MemberService(db).expire_points(),
        "mark_dormant": lambda: MemberService(db).mark_dormant(),
        "refresh_grades": lambda: MemberService(db).refresh_all_grades(),
        "best_reviews": lambda: ReviewService(db).mark_best_reviews(),
    }

    # 요청한 이름에 해당하는 배치 작업을 찾는다.
    job = jobs.get(job_name)

    if job is None:
        # 목록에 없는 작업 이름이면 실행하지 않는다.
        raise BusinessError(
            f"지원하지 않는 배치입니다: {job_name}"
        )

    # 선택한 배치 작업을 실행하고 처리 건수를 받는다.
    affected = job()

    return {
        "job": job_name,
        "affected": affected,
    }
