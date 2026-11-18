"""AI 학습 파이프라인 오케스트레이션.

여러 AI 모델의 학습 작업을 순서대로 실행하고, 실행 결과를 기록한다.
모든 모델의 실행 이력은 ai.model_runs 테이블에 저장한다.
APScheduler 또는 외부 크론에서 run_all()을 호출해 정기 배치로 운영할 수 있다.
"""
import logging
import time
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from team_backend.app.core.config import settings

logger = logging.getLogger(__name__)


@contextmanager
def model_run(
    db: Session,
    model_name: str,
    model_version: str,
    params: Optional[Dict] = None,
):
    """모델 실행의 시작과 끝, 성공 여부를 데이터베이스에 기록한다.

    with 문 안에서 작업이 성공하면 SUCCESS,
    예외가 발생하면 FAILED 상태를 기록한다.
    """
    import json

    # 실행 시간을 재기 위해 고해상도 타이머의 시작값을 저장한다.
    started = time.perf_counter()

    # 모델 실행을 시작할 때 RUNNING 상태의 이력을 먼저 만든다.
    # RETURNING run_id는 새로 생성된 실행 이력의 ID를 돌려준다.
    row = db.execute(
        text(
            """
            INSERT INTO ai.model_runs(model_name, model_version, status, params)
            VALUES (:n, :v, 'RUNNING', CAST(:p AS jsonb))
            RETURNING run_id
            """
        ),
        {
            "n": model_name,
            "v": model_version,
            # 실행에 사용한 설정값을 JSON으로 저장한다.
            "p": json.dumps(params or {}, ensure_ascii=False),
        },
    ).first()

    # 실행 이력을 먼저 저장해 이후 작업이 실패해도 시작 기록이 남게 한다.
    db.commit()

    run_id = int(row[0])

    # with 문 안의 학습 함수가 실행 중에 이 딕셔너리에 결과를 기록한다.
    state: Dict = {
        "run_id": run_id,
        "row_count": 0,
        "metrics": {},
    }

    try:
        # 이 줄에서 with 문 안의 실제 모델 학습 코드가 실행된다.
        yield state

    except Exception as exc:
        # 작업 중 오류가 발생했으면 진행 중인 DB 변경을 취소한다.
        db.rollback()

        # 실행 이력을 실패 상태로 바꾸고 오류 메시지와 종료 시간을 저장한다.
        db.execute(
            text(
                """
                UPDATE ai.model_runs
                   SET status = 'FAILED',
                       error_message = :e,
                       finished_at = now()
                 WHERE run_id = :r
                """
            ),
            {
                # 오류 메시지가 너무 길어지지 않도록 최대 2000자로 제한한다.
                "e": str(exc)[:2000],
                "r": run_id,
            },
        )
        db.commit()

        # 오류와 함께 호출 경로도 로그에 기록한다.
        logger.exception("모델 실행 실패: %s", model_name)

        # 오류를 다시 발생시켜 호출한 쪽에서도 실패를 알 수 있게 한다.
        raise

    else:
        # 예외 없이 작업이 끝난 경우 실행 시간을 초 단위로 계산한다.
        elapsed = round(time.perf_counter() - started, 3)
        state["metrics"]["elapsed_seconds"] = elapsed

        # 실행 이력을 성공 상태로 바꾸고 처리 건수와 성능 지표를 저장한다.
        db.execute(
            text(
                """
                UPDATE ai.model_runs
                   SET status = 'SUCCESS',
                       row_count = :c,
                       metrics = CAST(:m AS jsonb),
                       finished_at = now()
                 WHERE run_id = :r
                """
            ),
            {
                "c": state["row_count"],
                "m": json.dumps(
                    state["metrics"],
                    ensure_ascii=False,
                    default=str,
                ),
                "r": run_id,
            },
        )
        db.commit()

        logger.info("모델 실행 완료: %s (%.3fs)", model_name, elapsed)


class AiPipeline:
    """프로젝트의 AI 모델 학습과 배치 작업을 실행하는 클래스."""

    def __init__(self, db: Session):
        # 각각의 학습 작업에서 사용할 데이터베이스 연결을 보관한다.
        self.db = db

    # ------------------------------------------------------------- 추천 모델
    def train_recommender(self) -> Dict:
        """추천 모델을 학습하고 추천 결과를 데이터베이스에 저장한다."""
        # 필요한 모듈은 실제 작업을 실행할 때 가져온다.
        # 이렇게 하면 해당 기능을 쓰지 않을 때 불필요한 로딩을 줄일 수 있다.
        from team_backend.app.ai.recommender import (
            CollaborativeFilteringRecommender,
            invalidate_recommender,
        )

        # 학습 전체를 model_run으로 감싸 성공 또는 실패 이력을 남긴다.
        with model_run(self.db, "recommender", "cf-v1") as state:
            recommender = CollaborativeFilteringRecommender(self.db)

            # DB에서 회원-도서 상호작용과 도서 정보를 읽어 온다.
            recommender.load_interactions()
            recommender.load_book_meta()

            # 도서 간 유사도를 계산해 추천 모델을 학습한다.
            metrics = recommender.fit()

            # 계산한 추천 결과를 DB에 저장한다.
            saved = recommender.persist()

            # 다음 요청에서 이전 추천기 캐시를 재사용하지 않도록 비운다.
            recommender.save_artifact()
            invalidate_recommender()

            # 실행 이력에 저장 건수와 모델 지표를 넣는다.
            state["row_count"] = saved
            state["metrics"].update(metrics)

            # 호출한 쪽에 보여 줄 결과를 반환한다.
            return {
                "model": "recommender",
                "saved": saved,
                **metrics,
            }

    def mine_association_rules(self) -> Dict:
        """함께 구매되는 도서 패턴을 찾아 연관 규칙으로 저장한다."""
        from team_backend.app.ai.recommender import AssociationRuleMiner

        with model_run(
            self.db,
            "association_rules",
            "apriori-pair-v1",
        ) as state:
            miner = AssociationRuleMiner(self.db)

            # 주문 데이터를 분석해 함께 구매된 도서 규칙을 계산한다.
            rules = miner.mine()

            # 계산한 규칙을 DB에 저장한다.
            saved = miner.persist(rules)

            state["row_count"] = saved
            state["metrics"] = {
                "rules": len(rules),
                "saved": saved,
            }

            return {
                "model": "association_rules",
                "rules": len(rules),
                "saved": saved,
            }

    # ------------------------------------------------------------- 감성 분석
    def train_sentiment(self) -> Dict:
        """리뷰 감성 분석 모델을 학습하고 모든 리뷰의 분석 결과를 갱신한다."""
        from team_backend.app.ai.sentiment import reload_analyzer

        with model_run(
            self.db,
            "sentiment",
            settings.SENTIMENT_MODEL_VERSION,
        ) as state:
            # 기존 감성 분석기를 다시 불러온다.
            analyzer = reload_analyzer()

            # DB에 저장된 리뷰와 별점을 이용해 감성 모델을 학습한다.
            metrics = analyzer.train_from_reviews(self.db)

            # 방금 학습한 모델이 적용되도록 분석기를 다시 불러온다.
            analyzer = reload_analyzer()

            # 새 모델로 전체 리뷰를 다시 분석해 결과를 저장한다.
            count = analyzer.reanalyze_all(self.db)

            state["row_count"] = count
            state["metrics"] = metrics

            return {
                "model": "sentiment",
                "analyzed": count,
                **metrics,
            }

    # ------------------------------------------------------------- 매출 집계·예측
    def refresh_sales(self, days: int = 400) -> Dict:
        """최근 일별 매출 데이터를 다시 집계한다."""
        from team_backend.app.ai.sales_analytics import SalesAnalytics

        # days 값도 실행 설정으로 기록한다.
        with model_run(
            self.db,
            "sales_etl",
            "etl-v1",
            {"days": days},
        ) as state:
            count = SalesAnalytics(self.db).refresh_daily(days)

            state["row_count"] = count
            return {
                "model": "sales_etl",
                "rows": count,
            }

    def train_forecast(self, horizon: Optional[int] = None) -> Dict:
        """매출 예측 모델을 학습하고 지정한 기간의 예측값을 저장한다."""
        from team_backend.app.ai.sales_analytics import (
            MODEL_VERSION,
            SalesAnalytics,
            SalesForecaster,
        )

        # 예측 기간이 생략되면 설정 파일의 기본 기간을 사용한다.
        horizon = horizon or settings.FORECAST_HORIZON_DAYS

        with model_run(
            self.db,
            "sales_forecast",
            MODEL_VERSION,
            {"horizon": horizon},
        ) as state:
            # 예측 전에 최근 매출 집계 자료를 최신 상태로 갱신한다.
            SalesAnalytics(self.db).refresh_daily(400)

            forecaster = SalesForecaster(self.db)

            # 과거 매출을 이용해 모델 계수를 학습한다.
            metrics = forecaster.fit()

            # 학습된 모델로 향후 매출을 예측한다.
            forecasts = forecaster.forecast(horizon)

            # 예측 결과를 데이터베이스에 저장한다.
            saved = forecaster.persist(forecasts)

            state["row_count"] = saved
            state["metrics"] = metrics

            return {
                "model": "sales_forecast",
                "saved": saved,
                **metrics,
            }

    # ------------------------------------------------------------- 회원 분석
    def train_segmentation(self, k: int = 4) -> Dict:
        """RFM 점수와 군집화를 이용해 고객 그룹을 계산하고 저장한다."""
        from team_backend.app.ai.customer_analytics import (
            SEGMENT_MODEL_VERSION,
            CustomerSegmentation,
        )

        # k는 고객을 몇 개의 군집으로 나눌지 정하는 값이다.
        with model_run(
            self.db,
            "customer_segment",
            SEGMENT_MODEL_VERSION,
            {"k": k},
        ) as state:
            segmentation = CustomerSegmentation(self.db)

            # 회원별 최근 구매일, 주문 횟수, 구매 금액을 바탕으로 RFM 점수를 계산한다.
            data = segmentation.compute()

            # 구매 특성이 비슷한 회원끼리 k개의 군집으로 나눈다.
            data = segmentation.cluster(data, k=k)

            # 계산한 세그먼트와 군집 결과를 DB에 저장한다.
            saved = segmentation.persist(data)

            state["row_count"] = saved
            state["metrics"] = {
                "members": saved,
                "clusters": k,
            }

            return {
                "model": "customer_segment",
                "members": saved,
            }

    def train_churn(self) -> Dict:
        """이탈 예측 모델을 학습하고 모든 회원의 이탈 가능성을 저장한다."""
        from team_backend.app.ai.customer_analytics import (
            CHURN_MODEL_VERSION,
            ChurnPredictor,
        )

        with model_run(
            self.db,
            "churn",
            CHURN_MODEL_VERSION,
        ) as state:
            predictor = ChurnPredictor(self.db)

            # 과거 회원 데이터를 이용해 이탈 예측 모델을 학습한다.
            metrics = predictor.fit()

            # 현재 회원별 이탈 확률과 위험 단계를 계산한다.
            predictions = predictor.predict_all()

            # 계산 결과를 데이터베이스에 저장한다.
            saved = predictor.persist(predictions)

            state["row_count"] = saved
            state["metrics"] = metrics

            return {
                "model": "churn",
                "scored": saved,
                **metrics,
            }

    # ------------------------------------------------------------------ 전체 학습
    def run_all(self) -> Dict:
        """모든 AI 작업을 차례대로 실행한다.

        한 작업이 실패해도 다음 작업은 계속 실행한다.
        """
        results = {}

        # 실행할 작업과 각 작업의 이름을 순서대로 준비한다.
        steps = [
            ("sales_etl", self.refresh_sales),
            ("sentiment", self.train_sentiment),
            ("recommender", self.train_recommender),
            ("association_rules", self.mine_association_rules),
            ("sales_forecast", self.train_forecast),
            ("customer_segment", self.train_segmentation),
            ("churn", self.train_churn),
        ]

        for name, func in steps:
            try:
                # 해당 작업을 실행하고 반환값을 이름에 연결해 저장한다.
                results[name] = func()
            except Exception as exc:  # 한 단계 실패가 전체 작업을 중단시키지 않게 한다.
                logger.error("%s 단계 실패: %s", name, exc)
                results[name] = {"error": str(exc)}

        return results

    # ------------------------------------------------------------------ 실행 이력 조회
    def recent_runs(self, limit: int = 20):
        """최근 AI 모델 실행 이력을 최신순으로 조회한다."""
        rows = self.db.execute(
            text(
                """
                SELECT run_id, model_name, model_version, status, row_count, metrics,
                       started_at, finished_at, error_message
                  FROM ai.model_runs
                 ORDER BY started_at DESC
                 LIMIT :lim
                """
            ),
            {"lim": limit},
        ).mappings().all()

        # SQLAlchemy 결과 행을 일반 딕셔너리 목록으로 바꿔 반환한다.
        return [dict(r) for r in rows]