"""매출 분석 및 판매 예측 모듈.

주요 기능
---------
* 일별 매출 집계 ETL: 주문 데이터를 날짜별로 모아 ai.sales_daily에 저장한다.
* 기간 매출 요약: 총 매출, 주문 수, 평균 주문 금액, 취소율, 성장률을 계산한다.
* 카테고리별 매출과 베스트셀러를 조회한다.
* Ridge 회귀로 미래 매출을 예측한다.
  NumPy가 없거나 학습 데이터가 부족하면 단순 평균 기반 예측으로 대체한다.
"""
import logging
import math
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings

logger = logging.getLogger(__name__)

# 학습된 예측 모델의 버전이다. 예측 결과를 저장할 때 어떤 모델을 썼는지 기록한다.
MODEL_VERSION = "ridge-ts-v1"

try:
    # 배열 계산과 행렬 연산에 사용할 라이브러리다.
    import numpy as np

    NUMPY_READY = True
except ImportError:  # NumPy가 설치되지 않은 환경
    NUMPY_READY = False
    logger.warning("NumPy 미설치: 이동평균 기반 단순 예측으로 대체합니다.")


# =============================================================================
# 매출 집계 및 통계
# =============================================================================
class SalesAnalytics:
    """데이터베이스의 매출 정보를 집계하고 분석하는 클래스."""

    def __init__(self, db: Session):
        # SQLAlchemy 데이터베이스 연결 객체를 보관한다.
        self.db = db

    # ------------------------------------------------------------------- ETL
    def refresh_daily(self, days: int = 400) -> int:
        """최근 N일의 주문·회원·방문 데이터를 날짜별로 다시 집계한다.

        집계 결과는 ai.sales_daily 테이블에 저장한다.
        같은 날짜의 데이터가 이미 있으면 새 데이터로 갱신한다.
        """
        sql = text(
            """
            INSERT INTO ai.sales_daily
                (stat_date, order_count, item_count, gross_amount, discount_amount,
                 net_amount, cancel_amount, new_member_cnt, visitor_cnt, avg_order_value)
            SELECT d.stat_date,
                   COALESCE(o.order_count, 0),
                   COALESCE(o.item_count, 0),
                   COALESCE(o.gross_amount, 0),
                   COALESCE(o.discount_amount, 0),
                   COALESCE(o.net_amount, 0),
                   COALESCE(c.cancel_amount, 0),
                   COALESCE(m.new_members, 0),
                   COALESCE(v.visitors, 0),
                   CASE WHEN COALESCE(o.order_count, 0) = 0 THEN 0
                        ELSE COALESCE(o.net_amount, 0) / o.order_count END
              -- 집계할 날짜 목록을 만든다. 오늘을 포함해 최근 지정 일수의 날짜가 생성된다.
              FROM (SELECT generate_series(
                             CURRENT_DATE - (:days || ' days')::interval,
                             CURRENT_DATE, '1 day')::date AS stat_date) d

              -- 결제가 완료된 주문의 날짜별 주문 수, 상품 수, 금액을 집계한다.
              LEFT JOIN (
                    SELECT o.ordered_at::date AS stat_date,
                           COUNT(DISTINCT o.order_id) AS order_count,
                           COALESCE(SUM(oi.quantity), 0) AS item_count,
                           COALESCE(SUM(o.item_amount), 0) AS gross_amount,
                           COALESCE(SUM(o.discount_amount + o.coupon_amount), 0) AS discount_amount,
                           COALESCE(SUM(o.total_amount), 0) AS net_amount
                      FROM shop.orders o
                      LEFT JOIN shop.order_items oi ON oi.order_id = o.order_id
                     WHERE o.status IN ('PAID','PREPARING','SHIPPING','DELIVERED','CONFIRMED')
                     GROUP BY o.ordered_at::date
              ) o ON o.stat_date = d.stat_date

              -- 취소된 주문 금액을 취소 처리 날짜별로 집계한다.
              LEFT JOIN (
                    SELECT cancelled_at::date AS stat_date, SUM(total_amount) AS cancel_amount
                      FROM shop.orders WHERE status = 'CANCELLED' AND cancelled_at IS NOT NULL
                     GROUP BY cancelled_at::date
              ) c ON c.stat_date = d.stat_date

              -- 신규 가입 회원 수를 가입 날짜별로 집계한다.
              LEFT JOIN (
                    SELECT created_at::date AS stat_date, COUNT(*) AS new_members
                      FROM shop.members GROUP BY created_at::date
              ) m ON m.stat_date = d.stat_date

              -- 방문 기록에서 날짜별 방문자 수를 계산한다.
              -- 로그인 회원은 member_id, 비회원은 session_key를 기준으로 중복을 줄인다.
              LEFT JOIN (
                    SELECT created_at::date AS stat_date,
                           COUNT(DISTINCT COALESCE(member_id::text, session_key)) AS visitors
                      FROM log.recent_views GROUP BY created_at::date
              ) v ON v.stat_date = d.stat_date

            -- 같은 날짜의 집계 자료가 이미 있으면 새 값으로 덮어쓴다.
            ON CONFLICT (stat_date) DO UPDATE
               SET order_count = EXCLUDED.order_count,
                   item_count = EXCLUDED.item_count,
                   gross_amount = EXCLUDED.gross_amount,
                   discount_amount = EXCLUDED.discount_amount,
                   net_amount = EXCLUDED.net_amount,
                   cancel_amount = EXCLUDED.cancel_amount,
                   new_member_cnt = EXCLUDED.new_member_cnt,
                   visitor_cnt = EXCLUDED.visitor_cnt,
                   avg_order_value = EXCLUDED.avg_order_value,
                   updated_at = now()
            """
        )

        # :days 자리에 days 값을 넣어 SQL을 실행한다.
        result = self.db.execute(sql, {"days": days})

        # 변경된 집계 결과를 데이터베이스에 확정한다.
        self.db.commit()

        logger.info("일별 매출 집계 완료: %d일", days)

        # 데이터베이스가 알려준 처리 건수를 반환한다.
        return result.rowcount or days

    # ------------------------------------------------------------------ 요약
    def summary(self, date_from: date, date_to: date) -> Dict:
        """지정한 기간의 매출 요약과 일별 내역을 반환한다."""
        sql = text(
            """
            SELECT COALESCE(SUM(order_count), 0)  AS total_orders,
                   COALESCE(SUM(net_amount), 0)   AS total_sales,
                   COALESCE(SUM(discount_amount), 0) AS total_discount,
                   COALESCE(SUM(cancel_amount), 0) AS cancel_amount,
                   COALESCE(SUM(item_count), 0)    AS item_count
              FROM ai.sales_daily
             WHERE stat_date BETWEEN :df AND :dt
            """
        )

        # 지정 기간의 일별 집계 자료를 합산한다.
        row = self.db.execute(
            sql, {"df": date_from, "dt": date_to}
        ).mappings().first() or {}

        # 데이터베이스에서 받은 값을 숫자로 변환한다.
        # 해당 값이 없으면 0을 사용한다.
        total_orders = int(row.get("total_orders") or 0)
        total_sales = float(row.get("total_sales") or 0)
        cancel_amount = float(row.get("cancel_amount") or 0)

        # 같은 날짜 수만큼 바로 앞선 기간을 구해 매출 성장률과 비교한다.
        span = (date_to - date_from).days + 1
        prev_from = date_from - timedelta(days=span)
        prev_to = date_from - timedelta(days=1)

        prev = self.db.execute(
            sql, {"df": prev_from, "dt": prev_to}
        ).mappings().first() or {}
        prev_sales = float(prev.get("total_sales") or 0)

        # 이전 기간 매출이 0이면 나눗셈을 할 수 없으므로 성장률을 0으로 둔다.
        growth = ((total_sales - prev_sales) / prev_sales * 100) if prev_sales else 0.0

        # 응답에 포함할 날짜별 매출 목록을 가져온다.
        daily = self.daily_series(date_from, date_to)

        return {
            "period_from": date_from,
            "period_to": date_to,
            "total_orders": total_orders,
            "total_sales": total_sales,
            "total_discount": float(row.get("total_discount") or 0),

            # 평균 주문 금액 = 총 매출 ÷ 주문 수
            "avg_order_value": (total_sales / total_orders) if total_orders else 0.0,

            # 취소율 = 취소 금액 ÷ (매출 + 취소 금액) × 100
            "cancel_rate": (cancel_amount / (total_sales + cancel_amount) * 100)
            if (total_sales + cancel_amount)
            else 0.0,

            "growth_rate": round(growth, 2),
            "daily": daily,
        }

    def daily_series(self, date_from: date, date_to: date) -> List[Dict]:
        """지정 기간의 날짜별 주문 수와 매출을 반환한다."""
        rows = self.db.execute(
            text(
                """
                SELECT stat_date, order_count, net_amount, avg_order_value
                  FROM ai.sales_daily
                 WHERE stat_date BETWEEN :df AND :dt
                 ORDER BY stat_date
                """
            ),
            {"df": date_from, "dt": date_to},
        ).all()

        # 각 데이터베이스 행을 API에서 쓰기 편한 딕셔너리로 바꾼다.
        return [
            {
                "stat_date": r[0],
                "order_count": int(r[1]),
                "net_amount": float(r[2]),
                "avg_order_value": float(r[3]),
            }
            for r in rows
        ]

    def monthly_series(self, months: int = 12) -> List[Dict]:
        """최근 지정 개월의 월별 주문 수와 매출을 반환한다."""
        rows = self.db.execute(
            text(
                """
                SELECT to_char(stat_date, 'YYYY-MM') AS ym,
                       SUM(order_count)::int, SUM(net_amount)::numeric
                  FROM ai.sales_daily
                 WHERE stat_date >= date_trunc('month', CURRENT_DATE) - (:m || ' months')::interval
                 GROUP BY ym ORDER BY ym
                """
            ),
            {"m": months},
        ).all()

        # 결과를 {"month": ..., "order_count": ..., "net_amount": ...} 형태로 변환한다.
        return [
            {"month": r[0], "order_count": int(r[1]), "net_amount": float(r[2])}
            for r in rows
        ]

    def category_sales(
        self, date_from: date, date_to: date, limit: int = 10
    ) -> List[Dict]:
        """지정 기간의 카테고리별 판매량과 매출을 반환한다."""
        rows = self.db.execute(
            text(
                """
                SELECT c.category_id, c.name,
                       COUNT(DISTINCT o.order_id)::int AS order_count,
                       SUM(oi.quantity)::int AS quantity,
                       SUM(oi.item_total)::numeric AS net_amount
                  FROM shop.orders o
                  JOIN shop.order_items oi ON oi.order_id = o.order_id
                  JOIN shop.books b ON b.book_id = oi.book_id
                  JOIN shop.categories c ON c.category_id = b.category_id
                 WHERE o.status IN ('PAID','PREPARING','SHIPPING','DELIVERED','CONFIRMED')
                   AND o.ordered_at::date BETWEEN :df AND :dt
                 GROUP BY c.category_id, c.name
                 ORDER BY net_amount DESC
                 LIMIT :lim
                """
            ),
            {"df": date_from, "dt": date_to, "lim": limit},
        ).all()

        # 조회된 카테고리들의 매출 합계다. 0으로 나누는 것을 막기 위해 기본값을 1로 둔다.
        total = sum(float(r[4]) for r in rows) or 1.0

        return [
            {
                "category_id": int(r[0]),
                "category_name": r[1],
                "order_count": int(r[2]),
                "quantity": int(r[3]),
                "net_amount": float(r[4]),

                # 각 카테고리가 조회 결과 총매출에서 차지하는 비율이다.
                "share": round(float(r[4]) / total * 100, 2),
            }
            for r in rows
        ]

    def best_sellers(
        self, date_from: date, date_to: date, limit: int = 10
    ) -> List[Dict]:
        """지정 기간에 많이 판매된 도서 목록을 반환한다."""
        rows = self.db.execute(
            text(
                """
                SELECT b.book_id, b.title, b.cover_image,
                       SUM(oi.quantity)::int AS quantity,
                       SUM(oi.item_total)::numeric AS net_amount,
                       COALESCE(string_agg(DISTINCT a.name, ', '), '') AS authors
                  FROM shop.orders o
                  JOIN shop.order_items oi ON oi.order_id = o.order_id
                  JOIN shop.books b ON b.book_id = oi.book_id
                  LEFT JOIN shop.book_authors ba ON ba.book_id = b.book_id
                  LEFT JOIN shop.authors a ON a.author_id = ba.author_id
                 WHERE o.status IN ('PAID','PREPARING','SHIPPING','DELIVERED','CONFIRMED')
                   AND o.ordered_at::date BETWEEN :df AND :dt
                 GROUP BY b.book_id, b.title, b.cover_image
                 ORDER BY quantity DESC
                 LIMIT :lim
                """
            ),
            {"df": date_from, "dt": date_to, "lim": limit},
        ).all()

        # 조회 순서대로 1위부터 순위를 붙여 반환한다.
        return [
            {
                "book_id": int(r[0]),
                "title": r[1],
                "cover_image": r[2],
                "quantity": int(r[3]),
                "net_amount": float(r[4]),

                # SQL에서 ", "로 연결한 작가 이름을 다시 리스트로 나눈다.
                "authors": [n for n in (r[5] or "").split(", ") if n],
                "rank": idx,
            }
            for idx, r in enumerate(rows, start=1)
        ]

    def hourly_distribution(self, days: int = 30) -> Dict[str, int]:
        """최근 N일 동안 주문이 들어온 시간대별 건수를 반환한다."""
        rows = self.db.execute(
            text(
                """
                SELECT EXTRACT(HOUR FROM ordered_at)::int AS h, COUNT(*)::int
                  FROM shop.orders
                 WHERE ordered_at >= now() - (:d || ' days')::interval
                 GROUP BY h ORDER BY h
                """
            ),
            {"d": days},
        ).all()

        # 주문이 한 건도 없는 시간도 0으로 나타나도록 00시부터 23시까지 먼저 만든다.
        result = {f"{h:02d}": 0 for h in range(24)}

        # 실제 주문이 있는 시간대의 값만 데이터베이스 결과로 덮어쓴다.
        for hour, count in rows:
            result[f"{int(hour):02d}"] = int(count)
        return result

    def weekday_distribution(self, days: int = 90) -> Dict[str, int]:
        """최근 N일 동안 주문이 들어온 요일별 건수를 반환한다."""
        # PostgreSQL의 DOW 값은 일요일이 0, 토요일이 6이다.
        labels = ["일", "월", "화", "수", "목", "금", "토"]

        rows = self.db.execute(
            text(
                """
                SELECT EXTRACT(DOW FROM ordered_at)::int AS d, COUNT(*)::int
                  FROM shop.orders
                 WHERE ordered_at >= now() - (:d || ' days')::interval
                 GROUP BY d ORDER BY d
                """
            ),
            {"d": days},
        ).all()

        # 주문이 없었던 요일도 0으로 보이게 기본값을 준비한다.
        result = {label: 0 for label in labels}

        # 데이터베이스의 요일 번호를 한글 요일 이름으로 바꿔 넣는다.
        for dow, count in rows:
            result[labels[int(dow)]] = int(count)
        return result

    def payment_method_share(self, days: int = 90) -> List[Dict]:
        """최근 N일 동안 결제 완료된 결제 수단별 건수와 금액 비중을 반환한다."""
        rows = self.db.execute(
            text(
                """
                SELECT p.method::text, COUNT(*)::int, SUM(p.amount)::numeric
                  FROM shop.payments p
                  JOIN shop.orders o ON o.order_id = p.order_id
                 WHERE p.status = 'PAID' AND p.approved_at >= now() - (:d || ' days')::interval
                 GROUP BY p.method ORDER BY 3 DESC
                """
            ),
            {"d": days},
        ).all()

        # 결제 수단별 결제 금액을 모두 합산한다.
        total = sum(float(r[2]) for r in rows) or 1.0

        return [
            {
                "method": r[0],
                "count": int(r[1]),
                "amount": float(r[2]),
                "share": round(float(r[2]) / total * 100, 2),
            }
            for r in rows
        ]


# =============================================================================
# 판매 예측
# =============================================================================
class SalesForecaster:
    """과거 일별 매출을 이용해 미래 매출을 예측하는 클래스."""

    def __init__(self, db: Session, alpha: float = 1.0):
        self.db = db

        # alpha는 Ridge 회귀의 규제 강도다.
        # 값이 커질수록 큰 계수가 만들어지는 것을 더 강하게 억제한다.
        self.alpha = alpha

        # 학습이 완료되면 여기에 회귀 계수를 저장한다.
        self.coefficients: Optional[List[float]] = None

        # 학습한 값과 실제 값의 차이(잔차)의 표준편차다.
        # 예측 결과의 상한과 하한 계산에 사용한다.
        self.residual_std: float = 0.0

        # 학습 성공 여부, 오차 지표 등을 저장한다.
        self.metrics: Dict = {}

    # ------------------------------------------------------------------ 피처
    @staticmethod
    def _build_features(
        index: int, target_day: date, history: List[float], ma7: float
    ) -> List[float]:
        """특정 날짜의 매출을 예측하는 데 사용할 숫자 목록을 만든다.

        이 숫자들을 설명 변수 또는 피처(feature)라고 부른다.
        """
        dow = target_day.weekday()  # 파이썬 기준: 월요일=0, 일요일=6

        # 첫 번째 1.0은 절편, index는 시간에 따른 증가/감소 추세를 나타낸다.
        features = [1.0, float(index)]

        # 요일별 표시값을 만든다.
        # 월요일은 기준 요일로 두고, 화요일부터 일요일까지 0 또는 1로 표현한다.
        features.extend([1.0 if dow == d else 0.0 for d in range(1, 7)])

        # 매월 1~5일이면 월초, 25일 이후면 월말로 표시한다.
        features.append(1.0 if target_day.day <= 5 else 0.0)
        features.append(1.0 if target_day.day >= 25 else 0.0)

        # 직전 7일 매출의 평균이다.
        features.append(ma7)

        # lag 1: 가장 최근 하루의 매출이다.
        features.append(history[-1] if history else 0.0)

        # lag 7: 7일 전 매출이다.
        # 기록이 7일보다 적으면 가장 최근 매출을 대신 사용한다.
        features.append(
            history[-7]
            if len(history) >= 7
            else (history[-1] if history else 0.0)
        )

        return features

    def _load_history(self, days: int = 365) -> List[Tuple[date, float]]:
        """최근 N일의 날짜별 매출을 오래된 날짜부터 읽어 온다."""
        rows = self.db.execute(
            text(
                """
                SELECT stat_date, net_amount::float FROM ai.sales_daily
                 WHERE stat_date >= CURRENT_DATE - (:d || ' days')::interval
                   AND stat_date < CURRENT_DATE
                 ORDER BY stat_date
                """
            ),
            {"d": days},
        ).all()

        # 각 행을 (날짜, 매출액) 형태의 튜플로 바꾼다.
        return [(r[0], float(r[1])) for r in rows]

    # ------------------------------------------------------------------ 학습
    def fit(self, days: int = 365) -> Dict:
        """과거 매출 자료로 회귀 모델의 계수를 계산한다."""
        history = self._load_history(days)

        # 데이터가 너무 적으면 안정적인 학습이 어렵기 때문에 중단한다.
        if len(history) < 30:
            self.metrics = {
                "trained": False,
                "reason": "insufficient history",
                "rows": len(history),
            }
            return self.metrics

        # 날짜와 매출을 각각 분리한다.
        values = [v for _, v in history]
        dates = [d for d, _ in history]

        rows_x: List[List[float]] = []
        rows_y: List[float] = []

        # 첫 7일은 이동평균과 7일 전 매출 피처를 충분히 만들 수 없어 제외한다.
        # 각 날짜의 피처(X)로 그 날짜의 실제 매출(y)을 맞추도록 학습 자료를 만든다.
        for i in range(7, len(values)):
            window = values[max(0, i - 7) : i]
            ma7 = sum(window) / len(window) if window else 0.0

            rows_x.append(
                self._build_features(i, dates[i], values[:i], ma7)
            )
            rows_y.append(values[i])

        # 이 모델은 NumPy의 행렬 계산 기능이 필요하다.
        if not NUMPY_READY:
            self.metrics = {"trained": False, "reason": "numpy not installed"}
            return self.metrics

        # 설명 변수(X)와 정답 매출(y)을 NumPy 배열로 바꾼다.
        x = np.array(rows_x, dtype=float)
        y = np.array(rows_y, dtype=float)

        # 큰 금액을 그대로 계산하면 수치 계산이 불안정해질 수 있어
        # 가장 큰 매출 크기를 기준으로 값을 축소한다.
        scale = max(float(np.max(np.abs(y))), 1.0)
        y_scaled = y / scale

        n_features = x.shape[1]

        # 회귀 계수에 규제를 적용할 때 사용하는 단위 행렬을 만든다.
        identity = np.eye(n_features)

        # 첫 번째 값은 절편이므로 규제 대상에서 제외한다.
        identity[0, 0] = 0.0

        # 피처 값의 크기도 서로 비슷해지도록 일부 값을 나눈다.
        x_scaled = x.copy()

        # 마지막 세 피처는 매출 금액과 관련된 값이므로 매출 크기로 축소한다.
        x_scaled[:, -3:] = x_scaled[:, -3:] / scale

        # 날짜 순번이 너무 커지지 않도록 전체 데이터 개수로 나눈다.
        x_scaled[:, 1] = x_scaled[:, 1] / max(len(values), 1)

        # Ridge 회귀의 정규방정식:
        # (X.T @ X + alpha * I) @ beta = X.T @ y
        # beta는 각 피처가 예측 결과에 얼마나 영향을 주는지 나타내는 계수다.
        xtx = x_scaled.T @ x_scaled + self.alpha * identity
        beta = np.linalg.solve(xtx, x_scaled.T @ y_scaled)

        # 학습 데이터에 대한 예측값과 실제값의 차이를 계산한다.
        pred = x_scaled @ beta
        residual = y_scaled - pred

        # 다음 예측에서 사용할 학습 결과를 객체에 보관한다.
        self.coefficients = beta.tolist()
        self.residual_std = float(np.std(residual) * scale)
        self._scale = scale
        self._n_history = len(values)

        # 모델의 설명력과 예측 오차를 계산한다.
        ss_total = float(np.sum((y_scaled - np.mean(y_scaled)) ** 2))
        ss_residual = float(np.sum(residual**2))
        mae = float(np.mean(np.abs(residual)) * scale)
        rmse = float(math.sqrt(np.mean(residual**2)) * scale)

        # MAPE는 실제 매출 대비 오차 비율이다.
        # 실제 매출이 0인 날짜는 나눗셈을 할 수 없어 계산에서 제외한다.
        nonzero = y != 0
        mape = (
            float(np.mean(np.abs(residual[nonzero] * scale / y[nonzero])) * 100)
            if nonzero.any()
            else 0.0
        )

        self.metrics = {
            "trained": True,
            "rows": len(rows_y),

            # R²는 모델이 매출 변화량을 얼마나 설명하는지 나타낸다.
            "r2": round(1 - ss_residual / ss_total, 4) if ss_total else 0.0,

            # MAE: 평균 절대 오차
            "mae": round(mae, 2),

            # RMSE: 큰 오차에 더 큰 영향을 주는 평균 오차 지표
            "rmse": round(rmse, 2),

            # MAPE: 실제값 대비 평균 오차의 백분율
            "mape": round(mape, 2),
            "alpha": self.alpha,
        }

        logger.info("판매 예측 모델 학습 완료: %s", self.metrics)
        return self.metrics

    # ------------------------------------------------------------------ 예측
    def forecast(self, horizon: Optional[int] = None) -> List[Dict]:
        """오늘부터 지정한 일수만큼의 매출을 예측한다."""
        # 기간을 전달하지 않으면 설정 파일에 있는 기본 기간을 사용한다.
        horizon = horizon or settings.FORECAST_HORIZON_DAYS

        history = self._load_history(365)

        # 과거 매출이 하나도 없으면 예측 결과를 만들 수 없다.
        if not history:
            return []

        values = [v for _, v in history]

        # 학습된 계수가 없거나 NumPy를 사용할 수 없으면 단순 예측으로 처리한다.
        if self.coefficients is None or not NUMPY_READY:
            return self._naive_forecast(history, horizon)

        beta = np.array(self.coefficients, dtype=float)
        scale = getattr(self, "_scale", 1.0)
        n_history = getattr(self, "_n_history", len(values))

        # working에는 과거 매출과, 반복 계산으로 만들어진 예측값을 함께 담는다.
        working = list(values)
        results: List[Dict] = []
        today = date.today()

        # 하루씩 순서대로 예측한다.
        for step in range(1, horizon + 1):
            target_day = today + timedelta(days=step - 1)

            # 예측 시점 직전 7일의 평균 매출을 계산한다.
            window = working[-7:]
            ma7 = sum(window) / len(window) if window else 0.0

            # 예측 날짜의 입력 피처를 만들고 학습 때와 같은 방식으로 크기를 조정한다.
            features = self._build_features(
                n_history + step, target_day, working, ma7
            )

            vector = np.array(features, dtype=float)
            vector[-3:] = vector[-3:] / scale
            vector[1] = vector[1] / max(n_history, 1)

            # 피처와 학습된 계수를 곱해 예측 매출을 구한다.
            predicted = float(vector @ beta) * scale

            # 매출 예측값이 음수가 되지 않도록 0보다 작으면 0으로 조정한다.
            predicted = max(predicted, 0.0)

            results.append(
                {
                    "target_date": target_day,
                    "predicted_amount": round(predicted),

                    # 잔차 표준편차를 사용해 예측 범위를 계산한다.
                    "lower_bound": round(
                        max(predicted - 1.96 * self.residual_std, 0)
                    ),
                    "upper_bound": round(
                        predicted + 1.96 * self.residual_std
                    ),
                }
            )

            # 다음 날짜를 예측할 때 오늘의 예측값도 과거 데이터처럼 사용한다.
            working.append(predicted)

        return results

    @staticmethod
    def _naive_forecast(
        history: List[Tuple[date, float]], horizon: int
    ) -> List[Dict]:
        """회귀 모델을 사용할 수 없을 때 요일별 평균으로 예측한다."""
        # 요일별 매출을 모아 둔다. 예: 월요일 매출 목록, 화요일 매출 목록
        by_dow: Dict[int, List[float]] = {}
        for d, v in history:
            by_dow.setdefault(d.weekday(), []).append(v)

        # 최근 28일 평균은 해당 요일의 기록이 부족할 때 대신 사용한다.
        overall = [v for _, v in history[-28:]]
        base = sum(overall) / len(overall) if overall else 0.0

        results = []
        today = date.today()

        for step in range(horizon):
            target = today + timedelta(days=step)

            # 과거 같은 요일의 매출 평균을 예측값으로 사용한다.
            samples = by_dow.get(target.weekday(), [])
            predicted = sum(samples) / len(samples) if samples else base

            # 단순 예측의 범위는 최근 평균 매출의 25%로 잡는다.
            spread = base * 0.25

            results.append(
                {
                    "target_date": target,
                    "predicted_amount": round(predicted),
                    "lower_bound": round(max(predicted - spread, 0)),
                    "upper_bound": round(predicted + spread),
                }
            )

        return results

    # ------------------------------------------------------------------ 저장
    def persist(self, forecasts: List[Dict], scope: str = "TOTAL") -> int:
        """예측 결과를 데이터베이스에 저장한다."""
        # 저장할 결과가 없다면 데이터베이스 작업 없이 0을 반환한다.
        if not forecasts:
            return 0

        # 같은 범위와 모델 버전으로 이전에 저장한 예측을 먼저 지운다.
        self.db.execute(
            text(
                "DELETE FROM ai.sales_forecasts WHERE scope = :s AND model_version = :v"
            ),
            {"s": scope, "v": MODEL_VERSION},
        )

        # INSERT 문에서 사용할 데이터 목록을 만든다.
        payload = [
            {
                "td": f["target_date"],
                "s": scope,
                "pa": f["predicted_amount"],
                "lb": f["lower_bound"],
                "ub": f["upper_bound"],
                "v": MODEL_VERSION,
            }
            for f in forecasts
        ]

        # 예측값과 예측 구간을 저장한다.
        self.db.execute(
            text(
                """
                INSERT INTO ai.sales_forecasts
                       (target_date, scope, predicted_amount, lower_bound, upper_bound, model_version)
                VALUES (:td, :s, :pa, :lb, :ub, :v)
                ON CONFLICT (target_date, scope, scope_key, model_version) DO NOTHING
                """
            ),
            payload,
        )

        # 저장 내용을 확정한다.
        self.db.commit()
        return len(payload)

    def next_days_total(self, days: int = 7) -> float:
        """데이터베이스에 저장된 향후 N일 예측 매출 합계를 반환한다."""
        row = self.db.execute(
            text(
                """
                SELECT COALESCE(SUM(predicted_amount), 0)::float
                  FROM ai.sales_forecasts
                 WHERE scope = 'TOTAL'
                   AND target_date BETWEEN CURRENT_DATE
                       AND CURRENT_DATE + (:d || ' days')::interval
                """
            ),
            {"d": days},
        ).first()

        # 조회 결과가 있으면 첫 번째 값을 반환하고, 없으면 0을 반환한다.
        return float(row[0]) if row else 0.0