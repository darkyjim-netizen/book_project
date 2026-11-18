"""AI 추천, 매출 분석, 회원 분석 API 라우터."""
from datetime import date, timedelta
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.orm import Session

from team_backend.app.core.config import settings
from team_backend.app.core.database import SessionLocal, get_db
from team_backend.app.core.security import get_current_member_optional, require_admin
from team_backend.app.models.member import Member
from team_backend.app.schemas.ai import (
    ChurnAnalysisResponse,
    CustomerAnalysisResponse,
    ForecastResponse,
    PurchaseAnalysisResponse,
    RecommendationResponse,
    RecommendedBook,
    SalesSummaryResponse,
    TrainResultResponse,
)
from team_backend.app.services.book_service import BookService


# 이 라우터에 등록된 API 주소는 모두 /ai로 시작한다.
router = APIRouter(prefix="/ai", tags=["AI"])


# =============================================================================
# 도서 추천
# =============================================================================
@router.get(
    "/recommendations",
    response_model=RecommendationResponse,
    summary="맞춤 추천",
)
def recommendations(
    limit: int = Query(12, ge=1, le=40),  # 추천 도서 수: 1~40개
    algorithm: str = Query(
        "item_cf",
        description="item_cf | user_cf | popular",
    ),
    db: Session = Depends(get_db),
    # 로그인 회원과 비회원 모두 이용할 수 있다.
    member=Depends(get_current_member_optional),
):
    """회원에게는 취향 기반 도서를, 비회원에게는 인기 도서를 추천한다."""

    # 추천 결과에 생성 시각을 기록할 때 사용한다.
    from datetime import datetime, timezone

    # 추천 시스템은 이 API에서 사용할 때 불러온다.
    from team_backend.app.ai.recommender import get_recommender

    recommender = get_recommender(db)

    # 로그인 여부와 요청한 알고리즘에 따라 추천 방식을 선택한다.
    if member is None:
        # 비회원은 과거 구매 정보가 없으므로 인기 도서로 시작한다.
        triples = recommender._cold_start(None, limit)
        algorithm_used = "POPULAR"

    elif algorithm == "user_cf":
        # 비슷한 회원들의 구매 기록을 바탕으로 추천한다.
        triples = recommender.user_based_recommend(
            member.member_id,
            limit,
        )
        algorithm_used = "USER_CF"

    elif algorithm == "popular":
        # 회원 여부와 관계없이 인기 도서 목록을 사용한다.
        triples = recommender._cold_start(
            member.member_id,
            limit,
        )
        algorithm_used = "POPULAR"

    else:
        # 기본값은 회원의 도서 이용 기록을 바탕으로 추천하는 item_cf다.
        triples = recommender.recommend_for_member(
            member.member_id,
            limit,
        )
        algorithm_used = "ITEM_CF"

    # 추천 결과의 도서 번호를 이용해 도서 상세 정보를 가져온다.
    book_service = BookService(db)
    books = {
        book.book_id: book
        for book in book_service.list_by_ids(
            [item[0] for item in triples]
        )
    }

    items = []

    # 추천 시스템의 결과(도서 번호, 추천 점수, 추천 이유)를 응답 객체로 바꾼다.
    for book_id, score, reason in triples:
        book = books.get(book_id)

        # 추천 도서가 삭제되었거나 조회되지 않으면 결과에서 제외한다.
        if book is None:
            continue

        items.append(
            RecommendedBook(
                book_id=book.book_id,
                title=book.title,
                authors=book.authors,
                cover_image=book.cover_image,
                sale_price=book.sale_price,
                rating_avg=book.rating_avg,
                score=score,
                reason=reason,
            )
        )

    # 사용한 알고리즘, 회원 번호, 생성 시각, 추천 목록을 반환한다.
    return RecommendationResponse(
        algorithm=algorithm_used,
        member_id=member.member_id if member else None,
        generated_at=datetime.now(timezone.utc),
        items=items,
    )


# =============================================================================
# 매출 분석
# =============================================================================
@router.get(
    "/sales/summary",
    response_model=SalesSummaryResponse,
    summary="매출 요약",
)
def sales_summary(
    date_from: Optional[date] = None,  # 조회 시작일
    date_to: Optional[date] = None,  # 조회 종료일
    _admin: Member = Depends(require_admin),  # 관리자만 이용 가능
    db: Session = Depends(get_db),
):
    """기간별 매출 요약과 일별 매출 추이를 반환한다."""

    from team_backend.app.ai.sales_analytics import SalesAnalytics

    # 종료일을 전달하지 않으면 오늘, 시작일을 전달하지 않으면 최근 30일로 설정한다.
    date_to = date_to or date.today()
    date_from = date_from or (date_to - timedelta(days=29))

    return SalesAnalytics(db).summary(date_from, date_to)


@router.get(
    "/sales/monthly",
    response_model=List[dict],
    summary="월별 매출",
)
def sales_monthly(
    months: int = Query(12, ge=1, le=36),  # 조회할 과거 개월 수
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """월별 매출 추이를 반환한다."""

    from team_backend.app.ai.sales_analytics import SalesAnalytics

    return SalesAnalytics(db).monthly_series(months)


@router.get(
    "/sales/categories",
    response_model=List[dict],
    summary="카테고리별 매출",
)
def sales_categories(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    limit: int = Query(10, ge=1, le=30),  # 반환할 카테고리 수
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """카테고리별 매출과 비중을 반환한다."""

    from team_backend.app.ai.sales_analytics import SalesAnalytics

    # 날짜가 빠지면 최근 30일을 기준으로 분석한다.
    date_to = date_to or date.today()
    date_from = date_from or (date_to - timedelta(days=29))

    return SalesAnalytics(db).category_sales(
        date_from,
        date_to,
        limit,
    )


@router.get(
    "/sales/best-sellers",
    response_model=List[dict],
    summary="기간 베스트셀러",
)
def sales_best_sellers(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    limit: int = Query(10, ge=1, le=50),  # 반환할 도서 수
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """지정 기간에 많이 판매된 도서를 반환한다."""

    from team_backend.app.ai.sales_analytics import SalesAnalytics

    # 날짜가 입력되지 않으면 최근 30일의 판매량을 기준으로 한다.
    date_to = date_to or date.today()
    date_from = date_from or (date_to - timedelta(days=29))

    return SalesAnalytics(db).best_sellers(
        date_from,
        date_to,
        limit,
    )


@router.get(
    "/sales/forecast",
    response_model=ForecastResponse,
    summary="판매 예측",
)
def sales_forecast(
    horizon: int = Query(30, ge=1, le=180),  # 예측할 미래 일수
    retrain: bool = Query(
        False,
        description="조회 시 즉시 재학습 여부",
    ),
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """회귀 모델을 학습해 앞으로의 매출을 예측한다."""

    from team_backend.app.ai.sales_analytics import (
        MODEL_VERSION,
        SalesAnalytics,
        SalesForecaster,
    )

    analytics = SalesAnalytics(db)
    forecaster = SalesForecaster(db)

    # retrain=True면 최근 400일 매출 데이터를 다시 정리한다.
    if retrain:
        analytics.refresh_daily(400)

    # 예측 모델을 학습하고 요청한 기간만큼 매출을 예측한다.
    metrics = forecaster.fit()
    forecasts = forecaster.forecast(horizon)

    # 계산한 예측 결과를 DB에 저장한다.
    forecaster.persist(forecasts)

    # 예측과 비교할 과거 60일 데이터를 조회한다.
    today = date.today()
    history = analytics.daily_series(
        today - timedelta(days=60),
        today - timedelta(days=1),
    )

    return ForecastResponse(
        model_version=MODEL_VERSION,
        horizon_days=horizon,
        metrics=metrics,
        history=history,
        forecast=forecasts,
    )


@router.get(
    "/sales/distribution",
    response_model=dict,
    summary="주문 시간/요일 분포",
)
def sales_distribution(
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """주문이 많이 발생하는 시간대와 요일, 결제 수단 비율을 반환한다."""

    from team_backend.app.ai.sales_analytics import SalesAnalytics

    analytics = SalesAnalytics(db)

    return {
        "hourly": analytics.hourly_distribution(),
        "weekday": analytics.weekday_distribution(),
        "payment_methods": analytics.payment_method_share(),
    }


# =============================================================================
# 회원 분석
# =============================================================================
@router.get(
    "/customers/analysis",
    response_model=CustomerAnalysisResponse,
    summary="회원 분석",
)
def customer_analysis(
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """회원 세그먼트, 재구매율, 평균 고객 가치 등을 반환한다."""

    from sqlalchemy import text

    from team_backend.app.ai.customer_analytics import CustomerSegmentation

    segmentation = CustomerSegmentation(db)

    # RFM 분석으로 회원 유형별 분포와 구매 현황을 구한다.
    segments = segmentation.segment_summary()
    overview = segmentation.purchase_overview()

    # 탈퇴하지 않은 전체 회원, 활성 회원, 최근 30일 신규 회원 수를 조회한다.
    row = (
        db.execute(
            text(
                """
                SELECT COUNT(*)::int AS total,
                       COUNT(*) FILTER (
                           WHERE status = 'ACTIVE'
                       )::int AS active,
                       COUNT(*) FILTER (
                           WHERE created_at >= now() - interval '30 days'
                       )::int AS new30
                FROM shop.members
                WHERE status <> 'WITHDRAWN'
                """
            )
        )
        .mappings()
        .first()
        or {}
    )

    # 회원의 예상 생애 가치(ltv_estimate) 평균을 구한다.
    ltv = db.execute(
        text(
            """
            SELECT COALESCE(AVG(ltv_estimate), 0)::float
            FROM ai.customer_segments
            """
        )
    ).first()

    # 클러스터 그룹별 회원 수를 구한다.
    clusters = db.execute(
        text(
            """
            SELECT COALESCE(cluster_label, '미분류'), COUNT(*)::int
            FROM ai.customer_segments
            GROUP BY cluster_label
            """
        )
    ).all()

    return CustomerAnalysisResponse(
        total_members=int(row.get("total") or 0),
        active_members=int(row.get("active") or 0),
        new_members_30d=int(row.get("new30") or 0),
        repurchase_rate=overview["repurchase_rate"],
        avg_ltv=float(ltv[0]) if ltv else 0.0,
        segments=segments,
        cluster_labels={
            row[0]: int(row[1])
            for row in clusters
        },
    )


@router.get(
    "/customers/purchase-analysis",
    response_model=PurchaseAnalysisResponse,
    summary="구매 분석",
)
def purchase_analysis(
    days: int = Query(90, ge=7, le=365),  # 분석 기간(일)
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """구매 패턴, 함께 구매한 상품, 시간대별 구매 정보를 반환한다."""

    from sqlalchemy import text

    from team_backend.app.ai.customer_analytics import CustomerSegmentation
    from team_backend.app.ai.sales_analytics import SalesAnalytics

    analytics = SalesAnalytics(db)
    segmentation = CustomerSegmentation(db)

    # 지정한 기간의 회원 구매 요약을 구한다.
    overview = segmentation.purchase_overview(days)

    date_to = date.today()
    date_from = date_to - timedelta(days=days)

    # 함께 구매되는 경향이 있는 도서 조합을 연관 규칙 테이블에서 가져온다.
    rules = (
        db.execute(
            text(
                """
                SELECT r.antecedent,
                       ba.title AS antecedent_title,
                       r.consequent,
                       bc.title AS consequent_title,
                       r.support::float,
                       r.confidence::float,
                       r.lift::float,
                       r.pair_count
                FROM ai.association_rules r
                JOIN shop.books ba ON ba.book_id = r.antecedent
                JOIN shop.books bc ON bc.book_id = r.consequent
                ORDER BY r.lift DESC, r.confidence DESC
                LIMIT 20
                """
            )
        )
        .mappings()
        .all()
    )

    # 지정 기간에 결제가 완료된 주문 수를 센다.
    total_orders = db.execute(
        text(
            """
            SELECT COUNT(*)::int
            FROM shop.orders
            WHERE ordered_at >= now() - (:d || ' days')::interval
              AND status IN (
                  'PAID',
                  'PREPARING',
                  'SHIPPING',
                  'DELIVERED',
                  'CONFIRMED'
              )
            """
        ),
        {"d": days},
    ).first()

    return PurchaseAnalysisResponse(
        total_orders=int(total_orders[0]) if total_orders else 0,
        avg_items_per_order=overview["avg_items_per_order"],
        avg_order_value=overview["avg_amount_per_member"],
        top_categories=analytics.category_sales(date_from, date_to),
        best_sellers=analytics.best_sellers(date_from, date_to),
        association_rules=[
            dict(rule)
            for rule in rules
        ],
        hourly_distribution=analytics.hourly_distribution(days),
        weekday_distribution=analytics.weekday_distribution(days),
    )


@router.get(
    "/customers/churn",
    response_model=ChurnAnalysisResponse,
    summary="이탈 예측 결과",
)
def churn_analysis(
    risk_level: Optional[str] = Query(
        None,
        description="HIGH | MID | LOW",
    ),
    limit: int = Query(50, ge=1, le=500),  # 한 번에 가져올 회원 수
    offset: int = Query(0, ge=0),  # 목록에서 건너뛸 회원 수
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """회원 이탈 예측 요약과 위험 회원 목록을 반환한다."""

    from team_backend.app.ai.customer_analytics import (
        CHURN_MODEL_VERSION,
        ChurnPredictor,
    )

    predictor = ChurnPredictor(db)

    # HIGH, MID, LOW 등 위험 등급별 회원 수와 회원 목록을 가져온다.
    summary = predictor.risk_summary()
    members = predictor.list_risk_members(
        risk_level,
        limit,
        offset,
    )

    from sqlalchemy import text

    # 가장 최근 성공한 이탈 예측 모델의 AUC 점수를 조회한다.
    auc_row = db.execute(
        text(
            """
            SELECT metrics->>'auc'
            FROM ai.model_runs
            WHERE model_name = 'churn'
              AND status = 'SUCCESS'
            ORDER BY started_at DESC
            LIMIT 1
            """
        )
    ).first()

    # 점수 데이터가 없거나 null이면 AUC를 None으로 반환한다.
    auc = (
        float(auc_row[0])
        if auc_row and auc_row[0] not in (None, "null")
        else None
    )

    return ChurnAnalysisResponse(
        model_version=CHURN_MODEL_VERSION,
        predicted_at=predictor.last_predicted_at(),
        total_scored=sum(summary.values()),
        high_risk_count=summary.get("HIGH", 0),
        mid_risk_count=summary.get("MID", 0),
        low_risk_count=summary.get("LOW", 0),
        auc=auc,
        members=members,
    )


@router.get(
    "/customers/churn/feature-importance",
    response_model=List[dict],
    summary="이탈 예측 피처 중요도",
)
def churn_importance(
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """이탈 예측 모델이 중요하게 사용한 항목을 반환한다."""

    from team_backend.app.ai.customer_analytics import ChurnPredictor

    predictor = ChurnPredictor(db)

    # 모델이 학습되어 있지 않으면 학습한 뒤 중요도를 계산한다.
    predictor.fit()
    return predictor.feature_importance()


# =============================================================================
# AI 모델 학습
# =============================================================================
def _run_pipeline(step: str) -> None:
    """백그라운드에서 지정한 AI 파이프라인 단계를 실행한다."""

    from team_backend.app.ai.pipeline import AiPipeline

    # BackgroundTasks에서는 요청 종료 후 사용할 DB 세션을 직접 만든다.
    db = SessionLocal()

    try:
        pipeline = AiPipeline(db)

        # step 문자열과 같은 이름의 파이프라인 메서드를 찾아 실행한다.
        getattr(pipeline, step)()

    finally:
        # 성공이나 실패에 관계없이 DB 연결을 닫는다.
        db.close()


@router.post(
    "/train/{model_name}",
    response_model=dict,
    summary="AI 모델 학습 실행",
)
def train_model(
    model_name: str,  # 학습할 모델 이름
    background: BackgroundTasks,
    async_mode: bool = Query(
        True,
        description="백그라운드 실행 여부",
    ),
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """요청한 AI 모델을 학습한다.

    사용할 수 있는 model_name:
    recommender, association, sentiment, forecast,
    segmentation, churn, sales_etl, all
    """

    from team_backend.app.ai.pipeline import AiPipeline
    from team_backend.app.core.exceptions import BusinessError

    # API 요청에서 받는 모델 이름을 실제 파이프라인 메서드 이름에 연결한다.
    mapping = {
        "recommender": "train_recommender",
        "association": "mine_association_rules",
        "sentiment": "train_sentiment",
        "forecast": "train_forecast",
        "segmentation": "train_segmentation",
        "churn": "train_churn",
        "sales_etl": "refresh_sales",
        "all": "run_all",
    }

    step = mapping.get(model_name)

    # 등록되지 않은 모델 이름이면 오류를 반환한다.
    if step is None:
        raise BusinessError(
            f"지원하지 않는 모델입니다: {model_name}"
        )

    if async_mode:
        # 백그라운드 실행을 선택하면 요청에는 대기 상태를 바로 반환한다.
        background.add_task(_run_pipeline, step)
        return {
            "model": model_name,
            "status": "QUEUED",
            "message": "백그라운드에서 학습을 시작했습니다.",
        }

    # 즉시 실행을 선택하면 학습이 끝날 때까지 기다린 뒤 결과를 반환한다.
    result = getattr(AiPipeline(db), step)()

    return {
        "model": model_name,
        "status": "DONE",
        "result": result,
    }


@router.get(
    "/model-runs",
    response_model=List[dict],
    summary="모델 실행 이력",
)
def model_runs(
    limit: int = Query(20, ge=1, le=100),  # 반환할 최근 실행 기록 수
    _admin: Member = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """AI 모델의 최근 학습·실행 기록을 반환한다."""

    from team_backend.app.ai.pipeline import AiPipeline

    return AiPipeline(db).recent_runs(limit)