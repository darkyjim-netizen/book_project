"""AI 분석, 추천, 관리자 대시보드에서 사용하는 응답 스키마."""
from datetime import date, datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


# -----------------------------------------------------------------------------
# 도서 추천
# -----------------------------------------------------------------------------
class RecommendedBook(BaseModel):
    """추천 목록에 표시할 도서 한 권의 정보."""

    book_id: int  # 도서 번호
    title: str  # 도서 제목
    authors: List[str] = []  # 저자 이름 목록
    cover_image: Optional[str] = None  # 표지 이미지 주소
    sale_price: float  # 판매 가격
    rating_avg: float  # 평균 별점
    score: float  # 추천 알고리즘이 계산한 추천 점수
    reason: Optional[str] = None  # 추천 이유. 예: 비슷한 책을 구매한 회원이 선택


class RecommendationResponse(BaseModel):
    """회원에게 보여줄 추천 결과 전체."""

    algorithm: str  # 사용한 추천 방식 또는 알고리즘 이름
    member_id: Optional[int] = None  # 추천 대상 회원. 비회원 추천이면 없을 수 있다.
    generated_at: datetime  # 추천 결과를 만든 시각
    items: List[RecommendedBook] = []  # 추천 도서 목록


class TrainResultResponse(BaseModel):
    """AI 모델 학습 또는 실행 결과."""

    model_name: str  # 모델 이름
    model_version: str  # 모델 버전
    status: str  # 실행 상태. 예: 완료, 실패
    row_count: int  # 처리한 데이터 행 수
    metrics: Dict = {}  # 정확도 등 모델 평가 수치를 담는 딕셔너리
    elapsed_seconds: float  # 작업에 걸린 시간(초)
    message: Optional[str] = None  # 추가 안내나 오류 메시지


# -----------------------------------------------------------------------------
# 매출 분석 / 예측
# -----------------------------------------------------------------------------
class SalesPoint(BaseModel):
    """하루치 매출 추이를 나타내는 데이터 한 건."""

    stat_date: date  # 통계 기준 날짜
    order_count: int  # 해당 날짜 주문 수
    net_amount: float  # 해당 날짜 순매출액
    avg_order_value: float  # 평균 주문 금액


class SalesSummaryResponse(BaseModel):
    """선택한 기간의 매출 요약과 일별 추이."""

    period_from: date  # 조회 기간 시작일
    period_to: date  # 조회 기간 마지막 날
    total_orders: int  # 기간 내 전체 주문 수
    total_sales: float  # 기간 내 총매출액
    total_discount: float  # 기간 내 총 할인액
    avg_order_value: float  # 평균 주문 금액
    cancel_rate: float  # 주문 취소 비율
    growth_rate: float  # 이전 기간과 비교한 매출 증가·감소율
    daily: List[SalesPoint] = []  # 날짜별 매출 자료


class CategorySales(BaseModel):
    """카테고리별 판매 실적."""

    category_id: int  # 카테고리 번호
    category_name: str  # 카테고리 이름
    order_count: int  # 해당 카테고리 상품이 포함된 주문 수
    quantity: int  # 판매된 상품 수량
    net_amount: float  # 해당 카테고리 순매출액
    share: float  # 전체 매출 중 해당 카테고리의 비율


class BestSeller(BaseModel):
    """베스트셀러 목록에 표시할 도서 실적."""

    book_id: int  # 도서 번호
    title: str  # 도서 제목
    authors: List[str] = []  # 저자 이름 목록
    cover_image: Optional[str] = None  # 표지 이미지 주소
    quantity: int  # 판매된 수량
    net_amount: float  # 해당 도서의 순매출액
    rank: int  # 판매 순위


class ForecastPoint(BaseModel):
    """특정 날짜의 매출 예측 결과 한 건."""

    target_date: date  # 매출을 예측한 날짜
    predicted_amount: float  # 예측 매출액
    lower_bound: Optional[float] = None  # 예측 범위의 하한
    upper_bound: Optional[float] = None  # 예측 범위의 상한


class ForecastResponse(BaseModel):
    """매출 예측 결과와 예측에 사용한 정보."""

    model_version: str  # 예측에 사용한 모델 버전
    horizon_days: int  # 예측 기간(일수)
    metrics: Dict = {}  # 예측 모델 평가 지표
    history: List[SalesPoint] = []  # 예측과 비교할 과거 매출 자료
    forecast: List[ForecastPoint] = []  # 미래 날짜별 예측 결과


# -----------------------------------------------------------------------------
# 회원 분석
# -----------------------------------------------------------------------------
class SegmentSummary(BaseModel):
    """RFM 등으로 나눈 회원 그룹 하나의 요약."""

    rfm_segment: str  # 회원 그룹 이름. 예: 신규, 우수, 휴면 위험
    member_count: int  # 해당 그룹에 속한 회원 수
    avg_monetary: float  # 그룹의 평균 구매 금액
    avg_frequency: float  # 그룹의 평균 구매 횟수
    avg_recency: float  # 마지막 구매 후 지난 평균 일수
    share: float  # 전체 회원 중 그룹이 차지하는 비율


class CustomerAnalysisResponse(BaseModel):
    """전체 회원의 구매 특성과 그룹 분포."""

    total_members: int  # 전체 회원 수
    active_members: int  # 활동 중인 회원 수
    new_members_30d: int  # 최근 30일 동안 가입한 회원 수
    repurchase_rate: float  # 재구매 회원 비율
    avg_ltv: float  # 회원 1명당 평균 예상 생애 구매액
    segments: List[SegmentSummary] = []  # 회원 그룹별 요약
    cluster_labels: Dict[str, int] = {}  # 군집 이름과 해당 회원 수


class ChurnRiskMember(BaseModel):
    """이탈 가능성이 높은 회원 한 명의 정보."""

    member_id: int  # 회원 번호
    name: str  # 회원 이름
    email_masked: str  # 개인정보 보호를 위해 일부를 가린 이메일
    grade_name: str  # 회원 등급
    churn_probability: float  # 모델이 계산한 이탈 가능성
    risk_level: str  # 위험 단계. 예: LOW, MID, HIGH
    recency_days: int  # 마지막 구매 후 지난 일수
    order_count: int  # 주문 횟수
    total_paid: float  # 누적 결제 금액
    top_features: Optional[Dict] = None  # 이탈 예측에 크게 영향을 준 요소


class ChurnAnalysisResponse(BaseModel):
    """회원 이탈 위험 분석의 전체 요약과 대상 회원 목록."""

    model_version: str  # 분석에 사용한 모델 버전
    predicted_at: Optional[datetime] = None  # 예측 실행 시각
    total_scored: int  # 이탈 가능성을 계산한 회원 수
    high_risk_count: int  # 고위험 회원 수
    mid_risk_count: int  # 중위험 회원 수
    low_risk_count: int  # 저위험 회원 수
    auc: Optional[float] = None  # 분류 모델 성능 지표. 값이 없을 수도 있다.
    members: List[ChurnRiskMember] = []  # 분석 대상 회원별 결과


class PurchaseAnalysisResponse(BaseModel):
    """구매 분석 결과. 장바구니에서 함께 구매된 상품 관계도 포함한다."""

    total_orders: int  # 분석 대상 주문 수
    avg_items_per_order: float  # 주문 1건당 평균 상품 수
    avg_order_value: float  # 평균 주문 금액
    top_categories: List[CategorySales] = []  # 판매가 많은 카테고리
    best_sellers: List[BestSeller] = []  # 판매가 많은 도서

    # 함께 구매되는 상품 관계 규칙을 담는다.
    # 예: A 도서를 구매한 고객이 B 도서도 구매하는 경향
    association_rules: List[Dict] = []

    hourly_distribution: Dict[str, int] = {}  # 시간대별 주문 수
    weekday_distribution: Dict[str, int] = {}  # 요일별 주문 수


# -----------------------------------------------------------------------------
# 관리자 대시보드
# -----------------------------------------------------------------------------
class DashboardKpi(BaseModel):
    """관리자 화면 상단에 표시할 핵심 수치."""

    today_orders: int  # 오늘 주문 수
    today_sales: float  # 오늘 매출
    today_members: int  # 오늘 가입한 회원 수
    today_reviews: int  # 오늘 작성된 리뷰 수
    waiting_qna: int  # 답변을 기다리는 Q&A 수
    open_chats: int  # 진행 중인 1:1 상담 수
    low_stock_books: int  # 재고가 부족한 도서 수
    sales_change_rate: float = 0.0  # 이전 비교 기간 대비 매출 변화율
    order_change_rate: float = 0.0  # 이전 비교 기간 대비 주문 수 변화율


class DashboardResponse(BaseModel):
    """관리자 대시보드 전체 응답."""

    kpi: DashboardKpi  # 상단 핵심 수치
    recent_orders: List[Dict] = []  # 최근 주문 목록
    sales_trend: List[SalesPoint] = []  # 날짜별 매출 추이
    best_sellers: List[BestSeller] = []  # 베스트셀러 목록
    category_sales: List[CategorySales] = []  # 카테고리별 판매 실적
    churn_high_risk: int = 0  # 이탈 고위험 회원 수
    sentiment_ratio: Dict[str, int] = {}  # 리뷰 감성별 개수 또는 비율
    forecast_next_7d: float = 0.0  # 앞으로 7일간 예상 매출