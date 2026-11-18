"""AI 분석 결과와 모델 실행 정보를 ai 스키마에 저장하는 ORM 모델."""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Integer,
    Numeric,  # 소수 자릿수를 지정할 수 있는 숫자 타입
    SmallInteger,
    String,
    Text,
    func,     # now() 같은 DB 함수
)
from sqlalchemy.dialects.postgresql import JSONB  # PostgreSQL JSON 데이터 저장 타입
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ModelRun(Base):
    """AI 모델을 학습하거나 실행한 기록."""

    __tablename__ = "model_runs"
    __table_args__ = {"schema": "ai"}

    run_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # 실행 기록 번호
    model_name: Mapped[str] = mapped_column(String(60), nullable=False)  # 모델 이름
    model_version: Mapped[str] = mapped_column(String(40), nullable=False)  # 모델 버전
    status: Mapped[str] = mapped_column(
        String(20),
        default="RUNNING",
    )  # 실행 상태. 예: 실행 중, 완료, 실패

    row_count: Mapped[int] = mapped_column(Integer, default=0)  # 처리한 데이터 행 수
    metrics: Mapped[Optional[dict]] = mapped_column(JSONB)  # 정확도 등 평가 지표를 JSON으로 저장
    params: Mapped[Optional[dict]] = mapped_column(JSONB)  # 학습에 사용한 설정값을 JSON으로 저장
    artifact_path: Mapped[Optional[str]] = mapped_column(String(255))  # 학습된 모델 파일 위치
    error_message: Mapped[Optional[str]] = mapped_column(Text)  # 실패한 경우 오류 내용

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )  # 실행 시작 시각
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )  # 실행 종료 시각. 아직 실행 중이면 비어 있을 수 있다.


class Recommendation(Base):
    """회원별 도서 추천 결과."""

    __tablename__ = "recommendations"
    __table_args__ = {"schema": "ai"}

    rec_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # 추천 결과 번호
    member_id: Mapped[int] = mapped_column(BigInteger, nullable=False)  # 추천 대상 회원
    book_id: Mapped[int] = mapped_column(BigInteger, nullable=False)  # 추천할 도서

    score: Mapped[float] = mapped_column(
        Numeric(8, 5),
        nullable=False,
    )  # 추천 점수. 점수가 높을수록 우선 추천할 수 있다.

    algorithm: Mapped[str] = mapped_column(
        String(30),
        default="ITEM_CF",
    )  # 추천 알고리즘 이름. ITEM_CF는 아이템 기반 협업 필터링을 뜻한다.

    rank: Mapped[int] = mapped_column(SmallInteger, default=0)  # 해당 회원의 추천 순위
    model_version: Mapped[str] = mapped_column(String(40), default="cf-v1")  # 사용한 모델 버전
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )  # 추천 결과 생성 시각


class BookSimilarity(Base):
    """도서 두 권이 얼마나 비슷한지 저장하는 테이블."""

    __tablename__ = "book_similarities"
    __table_args__ = {"schema": "ai"}

    # 도서 두 권과 알고리즘을 조합해 기본 키로 사용한다.
    # 같은 알고리즘으로 같은 도서 쌍을 중복 저장하지 않게 하는 구조다.
    book_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # 기준 도서
    similar_book_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # 비슷한 도서
    algorithm: Mapped[str] = mapped_column(
        String(30),
        primary_key=True,
        default="COSINE",
    )  # 유사도 계산 방식. 기본값 COSINE은 코사인 유사도 방식

    similarity: Mapped[float] = mapped_column(
        Numeric(8, 5),
        nullable=False,
    )  # 두 도서의 유사도 점수

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )  # 유사도 계산 결과를 갱신한 시각


class SalesDaily(Base):
    """하루 단위로 집계한 판매 통계."""

    __tablename__ = "sales_daily"
    __table_args__ = {"schema": "ai"}

    stat_date: Mapped[date] = mapped_column(Date, primary_key=True)  # 통계 기준 날짜
    order_count: Mapped[int] = mapped_column(Integer, default=0)  # 주문 수
    item_count: Mapped[int] = mapped_column(Integer, default=0)  # 판매된 상품 수량

    gross_amount: Mapped[float] = mapped_column(
        Numeric(14, 0),
        default=0,
    )  # 할인 전 매출액으로 사용하는 금액

    discount_amount: Mapped[float] = mapped_column(
        Numeric(14, 0),
        default=0,
    )  # 할인 금액 합계

    net_amount: Mapped[float] = mapped_column(
        Numeric(14, 0),
        default=0,
    )  # 할인 등을 반영한 순매출액으로 사용하는 금액

    cancel_amount: Mapped[float] = mapped_column(
        Numeric(14, 0),
        default=0,
    )  # 취소된 주문 금액

    new_member_cnt: Mapped[int] = mapped_column(Integer, default=0)  # 해당 날짜 신규 가입 회원 수
    visitor_cnt: Mapped[int] = mapped_column(Integer, default=0)  # 해당 날짜 방문자 수
    avg_order_value: Mapped[float] = mapped_column(
        Numeric(12, 2),
        default=0,
    )  # 평균 주문 금액

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )  # 통계를 갱신한 시각


class SalesForecast(Base):
    """미래 날짜의 예상 매출."""

    __tablename__ = "sales_forecasts"
    __table_args__ = {"schema": "ai"}

    forecast_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # 예측 결과 번호
    target_date: Mapped[date] = mapped_column(Date, nullable=False)  # 매출을 예측할 날짜

    scope: Mapped[str] = mapped_column(
        String(20),
        default="TOTAL",
    )  # 예측 범위. 예: 전체 매출 또는 특정 분류

    scope_key: Mapped[Optional[str]] = mapped_column(
        String(40)
    )  # 특정 분류를 예측할 때 사용하는 분류 식별값

    predicted_amount: Mapped[float] = mapped_column(
        Numeric(14, 0),
        nullable=False,
    )  # 예측한 매출액

    lower_bound: Mapped[Optional[float]] = mapped_column(
        Numeric(14, 0)
    )  # 예측 범위의 하한값
    upper_bound: Mapped[Optional[float]] = mapped_column(
        Numeric(14, 0)
    )  # 예측 범위의 상한값

    model_version: Mapped[str] = mapped_column(
        String(40),
        default="ridge-ts-v1",
    )  # 예측에 사용한 모델 버전

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )  # 예측 결과를 만든 시각


class CustomerSegment(Base):
    """RFM 분석과 군집화로 계산한 회원별 고객 분류 결과."""

    __tablename__ = "customer_segments"
    __table_args__ = {"schema": "ai"}

    # 회원마다 현재 분석 결과 한 건을 저장하는 구조다.
    member_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # RFM 분석에 사용하는 값
    recency_days: Mapped[int] = mapped_column(
        Integer,
        default=999,
    )  # 마지막 구매 후 지난 일수. 기본값 999는 오래 구매하지 않은 상태를 나타내는 데 쓰일 수 있다.

    frequency: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )  # 분석 기간 동안의 구매 횟수

    monetary: Mapped[float] = mapped_column(
        Numeric(14, 0),
        default=0,
    )  # 분석 기간 동안의 구매 금액

    # R, F, M 각각의 점수. 점수 계산 방식은 분석 코드에서 정한다.
    r_score: Mapped[int] = mapped_column(SmallInteger, default=1)  # 최근 구매 점수
    f_score: Mapped[int] = mapped_column(SmallInteger, default=1)  # 구매 빈도 점수
    m_score: Mapped[int] = mapped_column(SmallInteger, default=1)  # 구매 금액 점수

    rfm_segment: Mapped[str] = mapped_column(
        String(30),
        default="NEW",
    )  # RFM 점수 조합으로 정한 고객 유형

    cluster_id: Mapped[Optional[int]] = mapped_column(
        SmallInteger
    )  # 군집화 모델이 회원을 배정한 그룹 번호

    cluster_label: Mapped[Optional[str]] = mapped_column(
        String(40)
    )  # 그룹 번호에 붙인 사람이 읽기 쉬운 이름

    ltv_estimate: Mapped[Optional[float]] = mapped_column(
        Numeric(14, 0)
    )  # 회원이 장기적으로 지출할 것으로 예상하는 금액

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )  # 분석 결과를 갱신한 시각


class ChurnPrediction(Base):
    """회원별 이탈 가능성 예측 결과."""

    __tablename__ = "churn_predictions"
    __table_args__ = {"schema": "ai"}

    # 회원마다 현재 이탈 예측 결과 한 건을 저장하는 구조다.
    member_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    churn_probability: Mapped[float] = mapped_column(
        Numeric(6, 4),
        nullable=False,
    )  # 모델이 계산한 이탈 확률

    risk_level: Mapped[str] = mapped_column(
        String(10),
        default="LOW",
    )  # 확률을 구간으로 나눈 위험 수준. 예: LOW, MID, HIGH

    top_features: Mapped[Optional[dict]] = mapped_column(
        JSONB
    )  # 예측에 크게 영향을 준 요인들을 JSON으로 저장

    model_version: Mapped[str] = mapped_column(
        String(40),
        default="churn-lr-v1",
    )  # 이탈 예측에 사용한 모델 버전

    predicted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )  # 예측한 시각


class AssociationRule(Base):
    """함께 구매되는 상품의 관계를 저장하는 연관 규칙."""

    __tablename__ = "association_rules"
    __table_args__ = {"schema": "ai"}

    rule_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # 규칙 번호

    # antecedent는 먼저 조건으로 보는 상품, consequent는 함께 추천할 상품을 뜻한다.
    antecedent: Mapped[int] = mapped_column(BigInteger, nullable=False)  # 기준 도서 번호
    consequent: Mapped[int] = mapped_column(BigInteger, nullable=False)  # 함께 구매되는 도서 번호

    support: Mapped[float] = mapped_column(
        Numeric(8, 6),
        nullable=False,
    )  # 전체 거래 중 두 상품 조합이 함께 나온 비율

    confidence: Mapped[float] = mapped_column(
        Numeric(8, 6),
        nullable=False,
    )  # 기준 상품을 산 거래 중 다른 상품도 산 비율

    lift: Mapped[float] = mapped_column(
        Numeric(10, 4),
        nullable=False,
    )  # 두 상품의 연관성이 우연한 동시 구매보다 얼마나 강한지 나타내는 값

    pair_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )  # 두 상품을 함께 구매한 거래 수

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )  # 규칙을 계산하거나 갱신한 시각