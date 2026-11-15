"""Jinja2를 사용해 HTML 페이지를 서버에서 렌더링하는 라우터.

REST API와 같은 서비스 계층을 사용한다.
검색 엔진 노출이 필요한 쇼핑 페이지와 관리자 페이지를 담당한다.
"""
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_member_optional
from app.models.promotion import Banner
from app.schemas.book import BookSearchParams
from app.schemas.common import PageMeta
from app.services.book_service import BookService
from app.services.support_service import FaqService, NoticeService, QnaService


# 이 라우터의 페이지는 API 문서에 표시하지 않는다.
router = APIRouter(tags=["페이지"], include_in_schema=False)

# HTML 템플릿 파일을 찾을 폴더를 지정한다.
templates = Jinja2Templates(directory="app/templates")


# 주문 상태 코드를 화면에 표시할 한글 문구로 바꾼다.
STATUS_LABELS = {
    "PENDING": "결제 대기",
    "PAID": "결제 완료",
    "PREPARING": "상품 준비 중",
    "SHIPPING": "배송 중",
    "DELIVERED": "배송 완료",
    "CONFIRMED": "구매 확정",
    "CANCELLED": "주문 취소",
    "RETURN_REQ": "반품 접수",
    "RETURNED": "반품 완료",
    "EXCHANGE_REQ": "교환 접수",
    "EXCHANGED": "교환 완료",
}


# 이탈 예측에 사용한 데이터 항목 이름을 화면용 한글로 바꾼다.
FEATURE_LABELS = {
    "order_cnt": "주문 횟수",
    "total_amount_log": "누적 구매액",
    "avg_amount_log": "평균 주문액",
    "distinct_books": "구매 도서 종수",
    "review_cnt": "리뷰 수",
    "recency_days": "최근 구매 경과일",
    "login_recency_days": "최근 로그인 경과일",
    "tenure_days": "가입 기간",
    "order_per_month": "월 평균 주문",
    "grade_id": "회원 등급",
}


def _base_context(
    request: Request,
    db: Session,
    member,
) -> dict:
    """모든 HTML 템플릿에서 공통으로 사용할 데이터를 만든다."""

    # 메뉴에 표시할 활성화된 2단계 카테고리를 가져온다.
    roots = db.execute(
        text(
            """
            SELECT category_id, name
            FROM shop.categories
            WHERE depth = 2
              AND is_active = true
            ORDER BY parent_id, sort_order
            LIMIT 10
            """
        )
    ).all()

    # 템플릿은 이 딕셔너리의 값을 {{ 변수명 }} 형태로 사용할 수 있다.
    return {
        "request": request,
        "current_member": member,
        "nav_categories": [
            {
                "category_id": row[0],
                "name": row[1],
            }
            for row in roots
        ],
        "status_labels": STATUS_LABELS,
    }


# =============================================================================
# 쇼핑몰 페이지
# =============================================================================
@router.get(
    "/",
    response_class=HTMLResponse,
    summary="메인 페이지",
)
def index(
    request: Request,
    db: Session = Depends(get_db),
    member=Depends(get_current_member_optional),
):
    """메인 페이지에 추천 도서, 베스트셀러, 신간, 공지를 표시한다."""

    # AI 추천 모듈은 메인 페이지를 요청했을 때 불러온다.
    from app.ai.recommender import get_recommender

    book_service = BookService(db)
    recommender = get_recommender(db)

    # 로그인 회원에게는 회원별 추천을, 비회원에게는 인기 도서를 보여준다.
    if member is not None:
        triples = recommender.recommend_for_member(
            member.member_id,
            6,
        )
    else:
        triples = recommender._cold_start(None, 6)

    # 추천 결과에는 도서 번호가 들어 있으므로 실제 도서 정보를 조회한다.
    recommended = book_service.list_by_ids(
        [item[0] for item in triples]
    )

    # 메인 페이지에 노출할 최근 공지 5개를 가져온다.
    notices, _ = NoticeService(db).list_notices(1, 5)

    # 활성화된 배너 중 정렬 순서가 빠른 배너 3개를 가져온다.
    banners = list(
        db.query(Banner)
        .filter(Banner.is_active == True)  # noqa: E712
        .order_by(Banner.sort_order)
        .limit(3)
    )

    # 공통 메뉴 데이터에 메인 페이지 전용 데이터를 추가한다.
    context = _base_context(request, db, member)
    context.update(
        {
            "recommended": recommended,
            "bestsellers": book_service.list_bestsellers(6),
            "new_releases": book_service.list_new_releases(6),
            "notices": notices,
            "banners": banners,
            "keywords": book_service.popular_keywords(10),
        }
    )

    # 전달한 context 데이터를 shop/index.html 템플릿에서 HTML로 만든다.
    return templates.TemplateResponse(
        "shop/index.html",
        context,
    )


@router.get(
    "/search",
    response_class=HTMLResponse,
    summary="도서 검색 페이지",
)
def search(
    request: Request,
    keyword: Optional[str] = None,  # 검색어
    category_id: Optional[int] = None,  # 선택한 카테고리 번호
    sort: str = "recent",  # 정렬 방식
    page: int = Query(1, ge=1),  # 페이지 번호
    size: int = Query(20, ge=1, le=60),  # 한 페이지에 표시할 도서 수
    db: Session = Depends(get_db),
    member=Depends(get_current_member_optional),
):
    """도서 검색 결과 또는 카테고리별 도서 목록을 보여준다."""

    book_service = BookService(db)

    # 검색 조건을 하나의 객체로 모아 서비스에 전달한다.
    params = BookSearchParams(
        keyword=keyword,
        category_id=category_id,
        sort=sort,
        page=page,
        size=size,
    )

    # 검색 결과와 전체 검색 건수를 가져온다.
    # 로그인 회원 번호도 전달해 회원별 정보를 적용할 수 있게 한다.
    items, total = book_service.search(
        params,
        member.member_id if member else None,
    )
    meta = PageMeta.build(page, size, total)

    # 카테고리 페이지라면 화면에 표시할 카테고리 이름과 전체 경로를 조회한다.
    category = None
    if category_id:
        row = db.execute(
            text(
                """
                SELECT category_id, name, full_path
                FROM shop.categories
                WHERE category_id = :cid
                """
            ),
            {"cid": category_id},
        ).first()

        if row:
            category = {
                "category_id": row[0],
                "name": row[1],
                "full_path": row[2],
            }

    # 페이지 이동 링크에서 현재 검색 조건을 유지하기 위한 쿼리 문자열을 만든다.
    query_parts = []

    if keyword:
        query_parts.append(f"keyword={keyword}")

    if category_id:
        query_parts.append(f"category_id={category_id}")

    query_parts.append(f"sort={sort}")
    query_parts.append(f"size={size}")

    # 페이지 버튼에 표시할 시작·끝 페이지 번호를 계산한다.
    start_page = max(1, meta.page - 4)
    end_page = min(meta.total_pages, start_page + 9)

    context = _base_context(request, db, member)
    context.update(
        {
            "items": items,
            "meta": meta,
            "keyword": keyword,
            "category": category,
            "category_id": category_id,
            "sort": sort,
            "categories": book_service.category_tree(),
            "query_string": "&".join(query_parts),
            "start_page": start_page,
            "end_page": end_page,
        }
    )

    return templates.TemplateResponse(
        "shop/search.html",
        context,
    )


@router.get(
    "/books/{book_id}",
    response_class=HTMLResponse,
    summary="도서 상세 페이지",
)
def book_detail(
    book_id: int,
    request: Request,
    db: Session = Depends(get_db),
    member=Depends(get_current_member_optional),
):
    """도서 상세, 리뷰, 감성 통계와 추천 도서를 표시한다."""

    # 상세 페이지에서 필요한 추천 기능과 리뷰 서비스를 불러온다.
    from app.ai.recommender import AssociationRuleMiner, get_recommender
    from app.services.review_service import ReviewService

    book_service = BookService(db)
    review_service = ReviewService(db)

    # 도서 정보를 조회하면서 조회수도 증가시킨다.
    entity = book_service.get_book(
        book_id,
        increase_view=True,
    )

    # 로그인 회원 번호 또는 비회원 세션 키를 이용해 도서 조회 기록을 남긴다.
    book_service.record_view(
        book_id,
        member.member_id if member else None,
        request.cookies.get("cart_session"),
    )

    # 상세 페이지에 필요한 도서 응답 데이터를 만든다.
    detail = book_service.to_detail(
        entity,
        member.member_id if member else None,
    )

    # 최신 리뷰 10개와 해당 도서의 별점·감성 통계를 가져온다.
    reviews, _ = review_service.list_by_book(
        book_id,
        1,
        10,
        "recent",
        None,
        None,
        member.member_id if member else None,
    )
    stats = review_service.book_stats(book_id)

    # 내용이 비슷한 도서와 함께 구매되는 도서를 각각 조회한다.
    recommender = get_recommender(db)

    similar = book_service.list_by_ids(
        [
            book_id
            for book_id, _ in recommender.similar_books(book_id, 5)
        ]
    )

    together = book_service.list_by_ids(
        [
            book_id
            for book_id, _ in AssociationRuleMiner(db)
            .frequently_bought_together(book_id, 5)
        ]
    )

    context = _base_context(request, db, member)
    context.update(
        {
            "book": detail,
            "reviews": reviews,
            "stats": stats,
            "similar": similar,
            "together": together,
        }
    )

    return templates.TemplateResponse(
        "shop/book_detail.html",
        context,
    )


@router.get(
    "/notice",
    response_class=HTMLResponse,
    summary="공지사항 목록 페이지",
)
def notice_list(
    request: Request,
    page: int = Query(1, ge=1),
    category: Optional[str] = None,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    member=Depends(get_current_member_optional),
):
    """공지사항 목록 페이지를 보여준다."""

    # 공지 목록과 전체 건수를 조회한다.
    rows, total = NoticeService(db).list_notices(
        page,
        10,
        category,
        keyword,
    )

    context = _base_context(request, db, member)
    context.update(
        {
            "items": rows,
            "meta": PageMeta.build(page, 10, total),
            "category": category,
            "keyword": keyword,
        }
    )

    return templates.TemplateResponse(
        "shop/notice.html",
        context,
    )


@router.get(
    "/notice/{notice_id}",
    response_class=HTMLResponse,
    summary="공지 상세 페이지",
)
def notice_detail(
    notice_id: int,
    request: Request,
    db: Session = Depends(get_db),
    member=Depends(get_current_member_optional),
):
    """공지 본문과 이전·다음 공지 정보를 보여준다."""

    service = NoticeService(db)
    context = _base_context(request, db, member)

    # 템플릿에서 공지 내용과 이전·다음 글을 사용할 수 있게 전달한다.
    context.update(
        {
            "notice": service.get_notice(notice_id),
            "adjacent": service.get_adjacent(notice_id),
        }
    )

    return templates.TemplateResponse(
        "shop/notice_detail.html",
        context,
    )


@router.get(
    "/faq",
    response_class=HTMLResponse,
    summary="FAQ 페이지",
)
def faq_page(
    request: Request,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    member=Depends(get_current_member_optional),
):
    """FAQ 목록과 카테고리를 보여준다."""

    service = FaqService(db)
    context = _base_context(request, db, member)
    context.update(
        {
            "faqs": service.list_faqs(category),
            "categories": service.categories(),
            "category": category,
        }
    )

    return templates.TemplateResponse(
        "shop/faq.html",
        context,
    )


@router.get(
    "/login",
    response_class=HTMLResponse,
    summary="로그인 페이지",
)
def login_page(
    request: Request,
    db: Session = Depends(get_db),
    member=Depends(get_current_member_optional),
):
    """로그인 페이지를 보여준다. 이미 로그인했다면 메인으로 이동한다."""

    if member is not None:
        return RedirectResponse("/", status_code=302)

    # 비회원 상태를 공통 컨텍스트에 넣어 로그인 템플릿을 렌더링한다.
    return templates.TemplateResponse(
        "shop/login.html",
        _base_context(request, db, None),
    )


@router.get("/logout", summary="로그아웃")
def logout_page():
    """로그인 쿠키를 삭제하고 메인 페이지로 이동한다."""

    response = RedirectResponse("/", status_code=302)

    # 브라우저에 저장된 액세스 토큰 쿠키를 삭제한다.
    response.delete_cookie("access_token")
    return response


@router.get(
    "/support/chat",
    response_class=HTMLResponse,
    summary="1:1 채팅상담 페이지",
)
def chat_page(
    request: Request,
    db: Session = Depends(get_db),
    member=Depends(get_current_member_optional),
):
    """채팅 페이지를 보여준다. 로그인 회원은 상담방을 준비한다."""

    context = _base_context(request, db, member)

    if member is not None:
        # 채팅 기능은 이 페이지에서 필요할 때만 불러온다.
        from app.services.chat_service import ChatService

        service = ChatService(db)

        # 회원의 기존 진행 중 상담방이 있으면 재사용하고, 없으면 새로 만든다.
        room = service.create_room(member, "1:1 문의")

        context.update(
            {
                "room": service.to_response(
                    room,
                    include_messages=True,
                ),
                # 채팅 페이지의 WebSocket 연결 인증에 사용할 토큰을 전달한다.
                "access_token": request.cookies.get("access_token", ""),
            }
        )

    return templates.TemplateResponse(
        "shop/chat.html",
        context,
    )


# =============================================================================
# 관리자 페이지
# =============================================================================
def _require_admin_page(member):
    """관리자가 아니면 로그인 페이지로 보내고, 관리자면 None을 반환한다."""

    if member is None or not member.is_admin:
        return RedirectResponse(
            "/login?next=/admin",
            status_code=302,
        )

    return None


@router.get(
    "/admin",
    response_class=HTMLResponse,
    summary="관리자 대시보드",
)
def admin_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    member=Depends(get_current_member_optional),
):
    """관리자 대시보드 화면을 보여준다."""

    # 관리자 권한이 없으면 로그인 페이지로 이동한다.
    guard = _require_admin_page(member)
    if guard:
        return guard

    # REST API에서 쓰는 대시보드 함수들을 호출해 같은 데이터를 재사용한다.
    from app.routers.admin import alerts as alerts_endpoint
    from app.routers.admin import dashboard as dashboard_endpoint

    data = dashboard_endpoint(member, db)
    alerts_data = alerts_endpoint(member, db)

    context = _base_context(request, db, member)
    context.update(
        {
            "active_menu": "dashboard",
            "data": data,
            "alerts": alerts_data,
        }
    )

    return templates.TemplateResponse(
        "admin/dashboard.html",
        context,
    )


@router.get(
    "/admin/analytics/sales",
    response_class=HTMLResponse,
    summary="매출 분석 페이지",
)
def admin_sales(
    request: Request,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    retrain: bool = False,
    db: Session = Depends(get_db),
    member=Depends(get_current_member_optional),
):
    """관리자용 매출 통계와 향후 매출 예측을 보여준다."""

    guard = _require_admin_page(member)
    if guard:
        return guard

    from app.ai.sales_analytics import (
        MODEL_VERSION,
        SalesAnalytics,
        SalesForecaster,
    )

    # 날짜를 입력하지 않으면 최근 30일을 조회한다.
    date_to = date_to or date.today()
    date_from = date_from or (date_to - timedelta(days=29))

    analytics = SalesAnalytics(db)

    # retrain=True로 요청하면 최근 400일 매출 데이터를 다시 정리한다.
    if retrain:
        analytics.refresh_daily(400)

    # 예측 모델을 학습하고 향후 30일의 매출을 계산한 뒤 저장한다.
    forecaster = SalesForecaster(db)
    metrics = forecaster.fit()
    forecasts = forecaster.forecast(30)
    forecaster.persist(forecasts)

    context = _base_context(request, db, member)
    context.update(
        {
            "active_menu": "sales",
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "summary": analytics.summary(date_from, date_to),
            "categories": analytics.category_sales(
                date_from,
                date_to,
            ),
            "distribution": {
                "hourly": analytics.hourly_distribution(),
                "weekday": analytics.weekday_distribution(),
            },
            "forecast": {
                "model_version": MODEL_VERSION,
                "horizon_days": 30,
                "metrics": metrics,
                "history": analytics.daily_series(
                    date.today() - timedelta(days=60),
                    date.today() - timedelta(days=1),
                ),
                "forecast": forecasts,
            },
        }
    )

    return templates.TemplateResponse(
        "admin/analytics_sales.html",
        context,
    )


@router.get(
    "/admin/analytics/churn",
    response_class=HTMLResponse,
    summary="이탈 예측 페이지",
)
def admin_churn(
    request: Request,
    risk_level: Optional[str] = "",
    db: Session = Depends(get_db),
    member=Depends(get_current_member_optional),
):
    """회원 이탈 위험 분석 결과를 관리자 화면에 보여준다."""

    guard = _require_admin_page(member)
    if guard:
        return guard

    from app.ai.customer_analytics import (
        CHURN_MODEL_VERSION,
        ChurnPredictor,
    )

    predictor = ChurnPredictor(db)

    # 모델을 준비하고 피처 중요도, 위험 등급별 인원, 위험 회원 목록을 가져온다.
    predictor.fit()
    importance = predictor.feature_importance()
    summary = predictor.risk_summary()
    members = predictor.list_risk_members(
        risk_level or None,
        100,
        0,
    )

    context = _base_context(request, db, member)
    context.update(
        {
            "active_menu": "churn",
            "risk_level": risk_level or "",
            "importance": importance,
            # 막대그래프 길이 계산에 사용할 가장 큰 중요도 값을 전달한다.
            "max_weight": (
                max(
                    (abs(item["weight"]) for item in importance),
                    default=1.0,
                )
                or 1.0
            ),
            "feature_labels": FEATURE_LABELS,
            "churn": {
                "model_version": CHURN_MODEL_VERSION,
                "predicted_at": predictor.last_predicted_at(),
                "total_scored": sum(summary.values()),
                "high_risk_count": summary.get("HIGH", 0),
                "mid_risk_count": summary.get("MID", 0),
                "low_risk_count": summary.get("LOW", 0),
                "auc": predictor.metrics.get("auc"),
                "members": members,
            },
        }
    )

    return templates.TemplateResponse(
        "admin/analytics_churn.html",
        context,
    )


@router.post(
    "/admin/analytics/churn/retrain",
    summary="이탈 모델 재학습",
)
def admin_churn_retrain(
    db: Session = Depends(get_db),
    member=Depends(get_current_member_optional),
):
    """이탈 예측 모델을 다시 학습하고 분석 페이지로 돌아간다."""

    guard = _require_admin_page(member)
    if guard:
        return guard

    from app.ai.pipeline import AiPipeline

    # 이탈 예측 학습 작업을 실행한다.
    AiPipeline(db).train_churn()

    # POST 처리 후 새로고침으로 같은 작업이 반복되지 않도록 이동 응답을 쓴다.
    return RedirectResponse(
        "/admin/analytics/churn",
        status_code=303,
    )


@router.get(
    "/admin/ai",
    response_class=HTMLResponse,
    summary="AI 모델 관리 페이지",
)
def admin_ai(
    request: Request,
    db: Session = Depends(get_db),
    member=Depends(get_current_member_optional),
):
    """AI 모델의 최근 학습·실행 기록을 보여준다."""

    guard = _require_admin_page(member)
    if guard:
        return guard

    from app.ai.pipeline import AiPipeline

    context = _base_context(request, db, member)
    context.update(
        {
            "active_menu": "ai",
            "runs": AiPipeline(db).recent_runs(30),
        }
    )

    return templates.TemplateResponse(
        "admin/ai_models.html",
        context,
    )


@router.post(
    "/admin/ai/train/{model_name}",
    summary="AI 모델 학습 실행(페이지)",
)
def admin_train(
    model_name: str,
    db: Session = Depends(get_db),
    member=Depends(get_current_member_optional),
):
    """관리자 페이지에서 지정한 AI 모델 학습을 실행한다."""

    guard = _require_admin_page(member)
    if guard:
        return guard

    from app.ai.pipeline import AiPipeline

    # URL에 사용하는 모델 이름과 실제 파이프라인 메서드를 연결한다.
    mapping = {
        "recommender": "train_recommender",
        "association": "mine_association_rules",
        "sentiment": "train_sentiment",
        "forecast": "train_forecast",
        "segmentation": "train_segmentation",
        "churn": "train_churn",
        "all": "run_all",
    }

    step = mapping.get(model_name)

    # 등록된 모델 이름일 때만 해당 학습 함수를 실행한다.
    if step:
        getattr(AiPipeline(db), step)()

    # 학습이 끝나면 AI 모델 관리 페이지로 돌아간다.
    return RedirectResponse(
        "/admin/ai",
        status_code=303,
    )