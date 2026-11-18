"""회원 분석 모듈: 구매 분석(RFM/세그먼트)과 고객 이탈 예측.

1. RFM 분석: 최근 구매일, 구매 횟수, 구매 금액으로 고객을 분류한다.
2. K-Means 군집화: 구매 특성이 비슷한 고객끼리 묶는다.
3. 이탈 예측: 과거 구매 정보로 고객의 이탈 가능성을 계산한다.
4. LTV 추정: 고객이 장기적으로 가져올 것으로 예상되는 매출을 계산한다.
"""
import logging
import math
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from team_backend.app.core.config import settings

logger = logging.getLogger(__name__)

# 예측 결과에 기록할 모델 버전 이름
CHURN_MODEL_VERSION = "churn-lr-v1"
SEGMENT_MODEL_VERSION = "rfm-kmeans-v1"

try:
    # 배열과 행렬 계산에 사용하는 라이브러리
    import numpy as np

    NUMPY_READY = True
except ImportError:  # NumPy가 설치되지 않은 경우
    NUMPY_READY = False

try:
    # 고객 군집화와 로지스틱 회귀에 사용할 라이브러리
    import sklearn  # noqa: F401

    SKLEARN_READY = True
except ImportError:  # scikit-learn이 설치되지 않은 경우
    SKLEARN_READY = False


# 이탈 예측 모델에 입력할 피처 이름이다.
# 순서는 모델 학습과 예측에서 동일하게 유지해야 한다.
CHURN_FEATURES = [
    "order_cnt",           # 주문 횟수
    "total_amount_log",    # 누적 구매 금액
    "avg_amount_log",      # 평균 주문 금액
    "distinct_books",      # 구매한 도서 종류 수
    "review_cnt",          # 작성한 리뷰 수
    "recency_days",        # 마지막 구매 후 지난 일수
    "login_recency_days",  # 마지막 로그인 후 지난 일수
    "tenure_days",         # 가입 후 지난 일수
    "order_per_month",     # 가입 기간 기준 월평균 주문 횟수
    "grade_id",            # 회원 등급 번호
]


# =============================================================================
# RFM 분석 및 고객 세그먼트
# =============================================================================
class CustomerSegmentation:
    """RFM 점수와 구매 특성을 이용해 고객을 분류한다."""

    def __init__(self, db: Session):
        # 데이터베이스에서 고객과 주문 정보를 조회할 때 사용한다.
        self.db = db

    def load_rfm(self) -> List[Dict]:
        """회원별 RFM 원본 값을 데이터베이스에서 조회한다.

        RFM은 다음 세 가지 구매 정보를 뜻한다.
        - Recency: 마지막 구매 이후 며칠이 지났는지
        - Frequency: 주문을 몇 번 했는지
        - Monetary: 총 얼마를 구매했는지
        """
        rows = self.db.execute(
            text(
                """
                SELECT m.member_id,
                       -- 마지막 주문 또는 가입일로부터 오늘까지 지난 일수
                       EXTRACT(DAY FROM now() - COALESCE(MAX(o.ordered_at), m.created_at))::int AS recency,

                       -- 주문이 없는 회원도 포함해 주문 횟수를 계산
                       COUNT(DISTINCT o.order_id)::int AS frequency,

                       -- 주문이 없는 경우 총 구매 금액은 0으로 처리
                       COALESCE(SUM(o.total_amount), 0)::numeric AS monetary
                  FROM shop.members m
                  LEFT JOIN shop.orders o
                         ON o.member_id = m.member_id
                        -- 결제가 완료되어 실제 구매로 볼 수 있는 주문만 포함
                        AND o.status IN ('PAID','PREPARING','SHIPPING','DELIVERED','CONFIRMED')
                 -- 탈퇴한 회원은 분석 대상에서 제외
                 WHERE m.status <> 'WITHDRAWN'
                 GROUP BY m.member_id, m.created_at
                """
            )
        ).all()

        # 데이터베이스 결과를 다루기 쉬운 딕셔너리 목록으로 변환한다.
        return [
            {
                "member_id": int(r[0]),
                # 값이 비어 있으면 오래전에 구매한 것으로 간주하도록 큰 값을 사용
                "recency_days": int(r[1] or 999),
                "frequency": int(r[2] or 0),
                "monetary": float(r[3] or 0),
            }
            for r in rows
        ]

    @staticmethod
    def _quintile_score(
        values: List[float], value: float, reverse: bool = False
    ) -> int:
        """값이 전체 회원 중 어느 5분위에 속하는지 1~5점으로 바꾼다.

        reverse=True이면 값이 작을수록 높은 점수를 준다.
        마지막 구매 후 지난 날짜는 작을수록 최근 구매이므로 역순 점수가 필요하다.
        """
        if not values:
            return 1

        # 전체 값을 오름차순으로 정렬한다.
        ordered = sorted(values)

        # 현재 값보다 작거나 같은 값이 전체에서 차지하는 비율을 구한다.
        position = sum(1 for v in ordered if v <= value) / len(ordered)

        # 비율을 1~5점으로 변환한다.
        score = min(int(position * 5) + 1, 5)

        # Recency처럼 값이 작을수록 좋은 항목은 점수를 반대로 바꾼다.
        return 6 - score if reverse else score

    @staticmethod
    def classify(r: int, f: int, m: int, order_cnt: int) -> str:
        """RFM 점수 조합에 따라 회원 그룹 이름을 정한다."""
        if order_cnt == 0:
            return "POTENTIAL"  # 아직 주문하지 않은 잠재 고객
        if r >= 4 and f >= 4 and m >= 4:
            return "VIP"  # 최근에도 자주, 많이 구매한 고객
        if f >= 4 and m >= 3:
            return "LOYAL"  # 구매 횟수가 많은 충성 고객
        if r >= 4 and f <= 2:
            return "NEW"  # 최근 구매했지만 아직 구매 횟수가 적은 고객
        if r == 3 and f >= 3:
            return "ACTIVE"  # 꾸준히 활동 중인 고객
        if r <= 2 and f >= 3:
            return "AT_RISK"  # 과거 구매는 많지만 최근 구매가 뜸한 고객
        if r <= 2 and m >= 4:
            return "CANT_LOSE"  # 과거 구매 금액이 커서 이탈 방지가 중요한 고객
        if r <= 1:
            return "DORMANT"  # 오랫동안 구매하지 않은 고객
        return "GENERAL"  # 위 조건에 해당하지 않는 일반 고객

    def compute(self) -> List[Dict]:
        """회원별 RFM 점수, 고객 그룹, 예상 LTV를 계산한다."""
        data = self.load_rfm()

        # 분석할 회원이 없으면 빈 목록을 반환한다.
        if not data:
            return []

        # 회원 전체의 각 RFM 값을 모은다.
        recencies = [d["recency_days"] for d in data]
        frequencies = [d["frequency"] for d in data]
        monetaries = [d["monetary"] for d in data]

        # 회원마다 RFM 점수와 그룹을 계산한다.
        for row in data:
            # Recency는 최근일수록 좋으므로 reverse=True를 사용한다.
            row["r_score"] = self._quintile_score(
                recencies, row["recency_days"], reverse=True
            )
            row["f_score"] = self._quintile_score(
                frequencies, row["frequency"]
            )
            row["m_score"] = self._quintile_score(
                monetaries, row["monetary"]
            )

            # 세 가지 점수와 주문 횟수를 이용해 고객 그룹을 정한다.
            row["rfm_segment"] = self.classify(
                row["r_score"],
                row["f_score"],
                row["m_score"],
                row["frequency"],
            )

            # 단순 LTV 추정식:
            # 평균 주문 금액 × 연간 구매 횟수 × 예상 유지 기간 2년
            avg_order = (
                row["monetary"] / row["frequency"]
                if row["frequency"]
                else 0.0
            )

            # 가입 또는 관측 기간을 바탕으로 연간 구매 횟수를 추정한다.
            # recency_days가 너무 작아 나눗셈이 불안정해지는 것을 막기 위해
            # 최소 0.25년을 사용한다.
            annual_freq = row["frequency"] / max(
                row["recency_days"] / 365.0, 0.25
            )

            # 연간 구매 횟수가 지나치게 크게 계산되면 최대 12회까지만 반영한다.
            row["ltv_estimate"] = round(
                avg_order * min(annual_freq, 12) * 2
            )

        return data

    # ------------------------------------------------------------------ K-Means 군집화
    def cluster(self, data: List[Dict], k: int = 4) -> List[Dict]:
        """RFM 원본값을 바탕으로 구매 특성이 비슷한 고객끼리 묶는다."""
        # 데이터가 없거나 NumPy가 없으면 군집 계산을 할 수 없다.
        if not data or not NUMPY_READY:
            for row in data:
                row["cluster_id"] = None
                row["cluster_label"] = None
            return data

        # 각 회원을 [최근 구매 경과일, 주문 횟수, 로그 변환한 구매 금액]으로 나타낸다.
        matrix = np.array(
            [
                [
                    row["recency_days"],
                    row["frequency"],
                    math.log1p(row["monetary"]),
                ]
                for row in data
            ],
            dtype=float,
        )

        # 변수마다 단위와 숫자 크기가 다르므로 평균과 표준편차를 이용해 표준화한다.
        mean = matrix.mean(axis=0)
        std = matrix.std(axis=0)

        # 표준편차가 0이면 나눗셈 오류가 나므로 1로 바꾼다.
        std[std == 0] = 1.0
        scaled = (matrix - mean) / std

        # 회원 수보다 군집 수가 많아지지 않도록 k를 조정한다.
        k = min(k, len(data))

        if SKLEARN_READY:
            # scikit-learn이 있으면 라이브러리의 K-Means를 사용한다.
            from sklearn.cluster import KMeans

            model = KMeans(n_clusters=k, n_init=10, random_state=42)
            labels = model.fit_predict(scaled)
            centers = model.cluster_centers_
        else:  # NumPy만 설치된 경우 직접 만든 K-Means를 사용
            labels, centers = self._kmeans_numpy(scaled, k)

        # 군집 중심값을 기준으로 군집을 정렬해 사람이 읽을 이름을 붙인다.
        # recency 값은 낮을수록 좋고, frequency와 monetary는 높을수록 좋다.
        ranking = sorted(
            range(len(centers)),
            key=lambda i: (
                -centers[i][1] - centers[i][2] + centers[i][0]
            ),
        )

        names = [
            "핵심 고객",
            "성장 고객",
            "일반 고객",
            "관리 필요 고객",
            "장기 미구매",
        ]

        # 정렬된 군집 번호와 사람이 읽을 이름을 연결한다.
        label_map = {
            cid: names[min(idx, len(names) - 1)]
            for idx, cid in enumerate(ranking)
        }

        # 계산된 군집 번호와 이름을 각 회원 데이터에 넣는다.
        for row, cid in zip(data, labels):
            row["cluster_id"] = int(cid)
            row["cluster_label"] = label_map.get(
                int(cid), f"군집 {int(cid)}"
            )

        return data

    @staticmethod
    def _kmeans_numpy(x, k: int, iterations: int = 100):  # pragma: no cover
        """scikit-learn이 없을 때 NumPy만으로 K-Means를 실행한다."""
        rng = np.random.default_rng(42)

        # 첫 번째 군집 중심을 무작위로 고른다.
        centers = [x[rng.integers(len(x))]]

        # K-Means++ 방식으로 기존 중심에서 멀리 떨어진 점을 다음 중심으로 선택한다.
        for _ in range(k - 1):
            distances = np.min(
                np.stack(
                    [np.sum((x - c) ** 2, axis=1) for c in centers]
                ),
                axis=0,
            )

            # 거리가 큰 점이 다음 중심으로 선택될 가능성을 높인다.
            probabilities = distances / (distances.sum() or 1.0)
            centers.append(x[rng.choice(len(x), p=probabilities)])

        centers = np.stack(centers)

        # 모든 회원을 일단 0번 군집에 넣고 시작한다.
        labels = np.zeros(len(x), dtype=int)

        for _ in range(iterations):
            # 각 회원과 각 군집 중심 사이의 거리를 계산한다.
            distances = np.stack(
                [np.sum((x - c) ** 2, axis=1) for c in centers]
            )

            # 각 회원을 가장 가까운 중심의 군집에 배정한다.
            new_labels = np.argmin(distances, axis=0)

            # 군집 배정이 더 이상 바뀌지 않으면 계산을 끝낸다.
            if np.array_equal(new_labels, labels):
                break

            labels = new_labels

            # 각 군집에 속한 회원들의 평균 위치를 새 중심으로 삼는다.
            for i in range(k):
                members = x[labels == i]
                if len(members):
                    centers[i] = members.mean(axis=0)

        return labels, centers

    # ------------------------------------------------------------------ 저장
    def persist(self, data: List[Dict]) -> int:
        """계산한 고객 세그먼트 결과를 데이터베이스에 저장한다."""
        if not data:
            return 0

        self.db.execute(
            text(
                """
                INSERT INTO ai.customer_segments
                       (member_id, recency_days, frequency, monetary, r_score, f_score, m_score,
                        rfm_segment, cluster_id, cluster_label, ltv_estimate)
                VALUES (:member_id, :recency_days, :frequency, :monetary, :r_score, :f_score,
                        :m_score, :rfm_segment, :cluster_id, :cluster_label, :ltv_estimate)

                -- 이미 저장된 회원이면 새 분석 결과로 갱신한다.
                ON CONFLICT (member_id) DO UPDATE
                   SET recency_days = EXCLUDED.recency_days,
                       frequency = EXCLUDED.frequency,
                       monetary = EXCLUDED.monetary,
                       r_score = EXCLUDED.r_score,
                       f_score = EXCLUDED.f_score,
                       m_score = EXCLUDED.m_score,
                       rfm_segment = EXCLUDED.rfm_segment,
                       cluster_id = EXCLUDED.cluster_id,
                       cluster_label = EXCLUDED.cluster_label,
                       ltv_estimate = EXCLUDED.ltv_estimate,
                       updated_at = now()
                """
            ),
            data,
        )

        # 저장 작업을 확정한다.
        self.db.commit()
        logger.info("고객 세그먼트 저장: %d명", len(data))
        return len(data)

    def segment_summary(self) -> List[Dict]:
        """고객 그룹별 회원 수와 평균 구매 정보를 요약한다."""
        rows = self.db.execute(
            text(
                """
                SELECT rfm_segment, COUNT(*)::int, AVG(monetary)::float,
                       AVG(frequency)::float, AVG(recency_days)::float
                  FROM ai.customer_segments
                 GROUP BY rfm_segment ORDER BY 2 DESC
                """
            )
        ).all()

        # 그룹별 회원 수를 모두 더한다.
        total = sum(int(r[1]) for r in rows) or 1

        return [
            {
                "rfm_segment": r[0],
                "member_count": int(r[1]),
                "avg_monetary": round(float(r[2] or 0), 2),
                "avg_frequency": round(float(r[3] or 0), 2),
                "avg_recency": round(float(r[4] or 0), 2),

                # 전체 회원 중 해당 그룹의 비율을 백분율로 계산한다.
                "share": round(int(r[1]) / total * 100, 2),
            }
            for r in rows
        ]

    def purchase_overview(self, days: int = 90) -> Dict:
        """회원들의 재구매율, 평균 구매액, 주문당 상품 수를 요약한다."""
        row = self.db.execute(
            text(
                """
                -- 회원마다 주문 횟수와 주문 금액 합계를 먼저 구한다.
                WITH member_orders AS (
                    SELECT member_id,
                           COUNT(*)::int AS cnt,
                           SUM(total_amount)::numeric AS amount
                      FROM shop.orders
                     WHERE member_id IS NOT NULL
                       AND status IN ('PAID','PREPARING','SHIPPING','DELIVERED','CONFIRMED')
                     GROUP BY member_id
                )
                SELECT COUNT(*)::int AS buyers,

                       -- 주문 횟수가 2회 이상인 회원 수
                       COUNT(*) FILTER (WHERE cnt >= 2)::int AS repeaters,

                       -- 회원별 총 구매 금액의 평균
                       COALESCE(AVG(amount), 0)::float AS avg_amount,

                       -- 회원별 주문 횟수의 평균
                       COALESCE(AVG(cnt), 0)::float AS avg_orders
                  FROM member_orders
                """
            )
        ).mappings().first() or {}

        # 각 주문에 포함된 상품 수를 구한 다음 평균을 계산한다.
        items = self.db.execute(
            text(
                """
                SELECT COALESCE(AVG(cnt), 0)::float FROM (
                    SELECT order_id, SUM(quantity)::int AS cnt
                      FROM shop.order_items GROUP BY order_id
                ) t
                """
            )
        ).first()

        buyers = int(row.get("buyers") or 0)
        repeaters = int(row.get("repeaters") or 0)

        return {
            "buyers": buyers,
            "repeaters": repeaters,

            # 재구매율 = 2회 이상 구매한 회원 수 ÷ 구매 회원 수 × 100
            "repurchase_rate": (
                round(repeaters / buyers * 100, 2) if buyers else 0.0
            ),
            "avg_amount_per_member": round(
                float(row.get("avg_amount") or 0), 2
            ),
            "avg_orders_per_member": round(
                float(row.get("avg_orders") or 0), 2
            ),
            "avg_items_per_order": round(
                float(items[0]) if items else 0.0, 2
            ),
        }


# =============================================================================
# 고객 이탈 예측
# =============================================================================
class ChurnPredictor:
    """로지스틱 회귀를 사용해 회원별 이탈 가능성을 계산한다."""

    def __init__(self, db: Session):
        self.db = db

        # 학습이 끝나면 모델의 가중치를 여기에 저장한다.
        self.weights: Optional[List[float]] = None

        # 로지스틱 회귀 계산에서 사용하는 절편이다.
        self.bias: float = 0.0

        # 학습 데이터 피처들의 평균과 표준편차다.
        # 예측 데이터도 학습 데이터와 같은 기준으로 표준화할 때 사용한다.
        self.mean: Optional[List[float]] = None
        self.std: Optional[List[float]] = None

        # 학습 성공 여부와 모델 성능 정보를 저장한다.
        self.metrics: Dict = {}

    # ------------------------------------------------------------------ 피처 만들기
    def _feature_sql(self) -> str:
        """기준 날짜(cutoff)까지의 회원 정보를 조회하는 SQL을 반환한다.

        이 SQL은 학습과 현재 회원 예측에서 공통으로 사용한다.
        """
        return """
            -- cutoff 이전에 가입한 탈퇴 회원이 아닌 회원을 분석 대상으로 삼는다.
            WITH base AS (
                SELECT m.member_id, m.created_at, m.grade_id, m.last_login_at
                  FROM shop.members m
                 WHERE m.status <> 'WITHDRAWN' AND m.created_at < :cutoff
            ),

            -- cutoff 이전의 구매 기록을 회원별로 요약한다.
            ord AS (
                SELECT o.member_id,
                       COUNT(DISTINCT o.order_id)::int AS order_cnt,
                       COALESCE(SUM(o.total_amount), 0)::float AS total_amount,
                       COALESCE(AVG(o.total_amount), 0)::float AS avg_amount,
                       COUNT(DISTINCT oi.book_id)::int AS distinct_books,
                       MAX(o.ordered_at) AS last_ordered_at
                  FROM shop.orders o
                  JOIN shop.order_items oi ON oi.order_id = o.order_id
                 WHERE o.ordered_at < :cutoff
                   AND o.status IN ('PAID','PREPARING','SHIPPING','DELIVERED','CONFIRMED')
                 GROUP BY o.member_id
            ),

            -- cutoff 전에 작성한 리뷰 수를 회원별로 센다.
            rv AS (
                SELECT member_id, COUNT(*)::int AS review_cnt
                  FROM shop.reviews
                 WHERE created_at < :cutoff
                 GROUP BY member_id
            ),

            -- cutoff 이후 구매한 회원을 찾는다.
            -- 학습할 때는 이후에 구매했는지를 이탈 라벨을 정하는 데 사용한다.
            future AS (
                SELECT DISTINCT member_id
                  FROM shop.orders
                 WHERE ordered_at >= :cutoff
                   AND status IN ('PAID','PREPARING','SHIPPING','DELIVERED','CONFIRMED')
            )

            -- 회원별 과거 피처와 이탈 여부를 한 행에 모아 반환한다.
            SELECT b.member_id,
                   COALESCE(o.order_cnt, 0) AS order_cnt,
                   COALESCE(o.total_amount, 0) AS total_amount,
                   COALESCE(o.avg_amount, 0) AS avg_amount,
                   COALESCE(o.distinct_books, 0) AS distinct_books,
                   COALESCE(r.review_cnt, 0) AS review_cnt,

                   -- 마지막 주문이 없으면 가입일을 기준으로 지난 날짜를 계산한다.
                   EXTRACT(DAY FROM :cutoff - COALESCE(o.last_ordered_at, b.created_at))::int
                       AS recency_days,

                   -- 마지막 로그인 날짜가 없으면 가입일을 기준으로 계산한다.
                   EXTRACT(DAY FROM :cutoff - COALESCE(b.last_login_at, b.created_at))::int
                       AS login_recency_days,

                   -- 가입 기간은 최소 1일로 설정해 0으로 나누는 것을 막는다.
                   GREATEST(EXTRACT(DAY FROM :cutoff - b.created_at)::int, 1)
                       AS tenure_days,

                   b.grade_id,

                   -- cutoff 이후 구매 기록이 없으면 churned=1, 있으면 0이다.
                   CASE WHEN f.member_id IS NULL THEN 1 ELSE 0 END AS churned
              FROM base b
              LEFT JOIN ord o ON o.member_id = b.member_id
              LEFT JOIN rv r ON r.member_id = b.member_id
              LEFT JOIN future f ON f.member_id = b.member_id
        """

    @staticmethod
    def _to_vector(row: Dict) -> List[float]:
        """회원 정보 한 행을 모델이 사용할 숫자 목록으로 바꾼다."""
        order_cnt = float(row["order_cnt"])
        tenure = float(row["tenure_days"]) or 1.0

        return [
            order_cnt,

            # 로그 변환으로 큰 금액의 차이를 완화한다.
            math.log1p(float(row["total_amount"])),
            math.log1p(float(row["avg_amount"])),

            float(row["distinct_books"]),
            float(row["review_cnt"]),
            float(row["recency_days"]),
            float(row["login_recency_days"]),
            tenure,

            # 가입 기간을 고려한 월평균 주문 횟수
            order_cnt / (tenure / 30.0),

            float(row["grade_id"]),
        ]

    def load_training_data(self, observation_days: Optional[int] = None):
        """모델 학습용 피처, 정답 라벨, 회원 ID를 만든다."""
        # 기간이 전달되지 않으면 설정값을 사용한다.
        observation_days = observation_days or settings.CHURN_INACTIVE_DAYS

        # 현재 시점에서 지정한 기간만큼 과거를 학습 기준 날짜로 정한다.
        cutoff = datetime.now(timezone.utc) - timedelta(days=observation_days)

        # cutoff 당시 회원 상태와 그 이후 구매 여부를 조회한다.
        rows = self.db.execute(
            text(self._feature_sql()), {"cutoff": cutoff}
        ).mappings().all()

        # 모델 입력값(X), 정답(y), 회원 ID를 각각 목록으로 분리한다.
        x = [self._to_vector(dict(r)) for r in rows]
        y = [int(r["churned"]) for r in rows]
        ids = [int(r["member_id"]) for r in rows]
        return x, y, ids

    def load_current_features(self):
        """현재 시점 기준으로 모든 회원의 예측용 피처를 만든다."""
        now = datetime.now(timezone.utc)

        # 현재 날짜를 cutoff로 전달한다.
        rows = self.db.execute(
            text(self._feature_sql()), {"cutoff": now}
        ).mappings().all()

        x = [self._to_vector(dict(r)) for r in rows]
        ids = [int(r["member_id"]) for r in rows]

        # 결과 화면이나 저장에 원본 회원 정보를 활용할 수 있도록 함께 반환한다.
        raw = [dict(r) for r in rows]
        return x, ids, raw

    # ------------------------------------------------------------------ 학습
    def fit(self, observation_days: Optional[int] = None) -> Dict:
        """학습 자료를 이용해 이탈 예측 모델을 학습한다."""
        x, y, _ids = self.load_training_data(observation_days)

        # 데이터가 적거나 이탈/비이탈 중 한 종류만 있으면 모델을 학습할 수 없다.
        if len(x) < 30 or len(set(y)) < 2:
            self.metrics = {
                "trained": False,
                "reason": "insufficient data",
                "rows": len(x),
                "positive": sum(y),
            }
            logger.warning("이탈 예측 학습 생략: %s", self.metrics)
            return self.metrics

        # 표준화와 행렬 계산을 위해 NumPy가 필요하다.
        if not NUMPY_READY:
            self.metrics = {
                "trained": False,
                "reason": "numpy not installed",
            }
            return self.metrics

        matrix = np.array(x, dtype=float)
        target = np.array(y, dtype=float)

        # 각 피처의 평균과 표준편차를 구해 저장한다.
        self.mean = matrix.mean(axis=0).tolist()
        std = matrix.std(axis=0)

        # 표준편차가 0인 피처는 1로 바꿔 0으로 나누는 것을 방지한다.
        std[std == 0] = 1.0
        self.std = std.tolist()

        # 모든 피처를 평균 0, 표준편차 1에 가까운 크기로 맞춘다.
        scaled = (matrix - np.array(self.mean)) / std

        if SKLEARN_READY:
            # scikit-learn이 설치되어 있으면 그 구현을 사용한다.
            metrics = self._fit_sklearn(scaled, target)
        else:  # scikit-learn이 없으면 NumPy로 직접 학습한다.
            metrics = self._fit_numpy(scaled, target)

        # 학습 결과에 데이터 건수와 이탈 회원 비율을 추가한다.
        metrics.update(
            {
                "trained": True,
                "rows": len(x),
                "churn_ratio": round(float(target.mean()), 4),
            }
        )

        self.metrics = metrics
        logger.info("이탈 예측 모델 학습 완료: %s", metrics)
        return metrics

    def _fit_sklearn(self, scaled, target) -> Dict:
        """scikit-learn 로지스틱 회귀 모델을 학습한다."""
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
        from sklearn.model_selection import train_test_split

        # 클래스 비율을 학습 자료와 시험 자료에 비슷하게 유지한다.
        stratify = target if len(set(target.tolist())) > 1 else None

        # 전체 데이터의 75%는 학습, 25%는 성능 확인에 사용한다.
        x_train, x_test, y_train, y_test = train_test_split(
            scaled,
            target,
            test_size=0.25,
            random_state=42,
            stratify=stratify,
        )

        # class_weight는 이탈/비이탈 데이터 수의 차이를 보정한다.
        model = LogisticRegression(
            max_iter=2000,
            class_weight="balanced",
            C=1.0,
        )
        model.fit(x_train, y_train)

        # 학습된 가중치와 절편을 보관해 이후 회원 예측에 활용한다.
        self.weights = model.coef_[0].tolist()
        self.bias = float(model.intercept_[0])

        # 시험 데이터의 이탈 확률과 0 또는 1 예측값을 구한다.
        proba = model.predict_proba(x_test)[:, 1]
        pred = (proba >= 0.5).astype(int)

        return {
            "accuracy": round(float(accuracy_score(y_test, pred)), 4),
            "f1": round(
                float(f1_score(y_test, pred, zero_division=0)), 4
            ),
            "auc": (
                round(float(roc_auc_score(y_test, proba)), 4)
                if len(set(y_test.tolist())) > 1
                else None
            ),
            "solver": "sklearn-logistic",
        }

    def _fit_numpy(
        self, scaled, target, epochs: int = 600, lr: float = 0.1
    ) -> Dict:  # pragma: no cover
        """NumPy만 사용해 경사하강법으로 로지스틱 회귀를 학습한다."""
        n_samples, n_features = scaled.shape

        # 처음에는 모든 피처의 영향력을 0으로 시작한다.
        weights = np.zeros(n_features)
        bias = 0.0

        # 이탈 회원 비율을 계산하고, 적은 쪽의 데이터에 더 큰 가중치를 준다.
        positive_ratio = target.mean() or 0.5
        sample_weight = np.where(
            target == 1,
            1 / positive_ratio,
            1 / (1 - positive_ratio),
        )

        # epochs 횟수만큼 예측과 가중치 수정을 반복한다.
        for _ in range(epochs):
            logits = scaled @ weights + bias

            # sigmoid 함수로 계산 결과를 0~1 사이 확률로 변환한다.
            pred = 1 / (1 + np.exp(-np.clip(logits, -30, 30)))

            # 실제값과 예측값의 차이를 구한다.
            error = (pred - target) * sample_weight

            # 오차가 줄어드는 방향으로 가중치와 절편을 조금씩 수정한다.
            weights -= (
                lr * (scaled.T @ error) / n_samples
                + lr * 0.01 * weights
            )
            bias -= lr * error.mean()

        self.weights = weights.tolist()
        self.bias = float(bias)

        # 학습 데이터에 대한 예측 정확도를 계산한다.
        logits = scaled @ weights + bias
        proba = 1 / (1 + np.exp(-np.clip(logits, -30, 30)))
        pred = (proba >= 0.5).astype(float)
        accuracy = float((pred == target).mean())

        return {
            "accuracy": round(accuracy, 4),
            "solver": "numpy-gradient-descent",
        }

    # ------------------------------------------------------------------ 예측
    def _sigmoid(self, value: float) -> float:
        """숫자를 0~1 사이의 확률로 바꾼다."""
        # 너무 큰 양수나 음수가 들어가 계산이 불안정해지는 것을 막는다.
        value = max(min(value, 30.0), -30.0)
        return 1.0 / (1.0 + math.exp(-value))

    def predict_one(self, vector: List[float]) -> float:
        """회원 한 명의 이탈 확률을 계산한다."""
        # 모델을 학습하지 못했다면 마지막 구매 경과일만 이용한 단순 추정값을 반환한다.
        if self.weights is None or self.mean is None or self.std is None:
            recency = vector[5]
            return min(
                recency / (settings.CHURN_INACTIVE_DAYS * 2),
                0.99,
            )

        # 절편에서 시작해 각 피처의 표준화 값과 가중치를 더한다.
        total = self.bias
        for value, mean, std, weight in zip(
            vector, self.mean, self.std, self.weights
        ):
            total += ((value - mean) / (std or 1.0)) * weight

        # 계산 결과를 0~1 확률로 변환한다.
        return self._sigmoid(total)

    @staticmethod
    def risk_level(probability: float) -> str:
        """이탈 확률에 따라 HIGH, MID, LOW 위험 단계를 정한다."""
        if probability >= settings.CHURN_THRESHOLD_HIGH:
            return "HIGH"
        if probability >= settings.CHURN_THRESHOLD_MID:
            return "MID"
        return "LOW"

    def feature_importance(self) -> List[Dict]:
        """모델 가중치의 절댓값을 기준으로 영향력이 큰 피처를 반환한다."""
        if not self.weights:
            return []

        # 피처 이름과 학습된 가중치를 짝지어 딕셔너리로 만든다.
        pairs = [
            {"feature": name, "weight": round(weight, 4)}
            for name, weight in zip(CHURN_FEATURES, self.weights)
        ]

        # 양수/음수 방향과 상관없이 영향력이 큰 순서로 정렬한다.
        return sorted(
            pairs,
            key=lambda p: abs(p["weight"]),
            reverse=True,
        )

    def predict_all(self) -> List[Dict]:
        """현재 회원 전체의 이탈 확률과 위험 등급을 계산한다."""
        x, ids, raw = self.load_current_features()

        # 피처 이름별 가중치를 빠르게 찾을 수 있도록 딕셔너리로 만든다.
        importance = {
            p["feature"]: p["weight"]
            for p in self.feature_importance()
        }

        results = []

        # 각 회원의 피처, 회원 ID, 원본 정보를 함께 순회한다.
        for vector, member_id, row in zip(x, ids, raw):
            probability = self.predict_one(vector)
            top_features = {}

            if importance and self.mean and self.std:
                # 각 피처가 예측에 기여한 정도를 계산한다.
                contributions = []
                for idx, name in enumerate(CHURN_FEATURES):
                    scaled = (
                        vector[idx] - self.mean[idx]
                    ) / (self.std[idx] or 1.0)

                    contributions.append(
                        (
                            name,
                            round(scaled * self.weights[idx], 4),
                        )
                    )

                # 영향이 큰 피처 네 개만 결과에 담는다.
                contributions.sort(
                    key=lambda c: abs(c[1]),
                    reverse=True,
                )
                top_features = dict(contributions[:4])
            else:
                # 모델을 사용하지 못한 경우 최근 구매 경과일을 참고 정보로 넣는다.
                top_features = {
                    "recency_days": row["recency_days"]
                }

            results.append(
                {
                    "member_id": member_id,
                    "churn_probability": round(probability, 4),
                    "risk_level": self.risk_level(probability),
                    "top_features": top_features,
                    "recency_days": int(row["recency_days"]),
                    "order_cnt": int(row["order_cnt"]),
                    "total_amount": float(row["total_amount"]),
                }
            )

        return results

    def persist(self, predictions: List[Dict]) -> int:
        """계산한 이탈 예측 결과를 데이터베이스에 저장한다."""
        import json

        if not predictions:
            return 0

        # SQL에 넣을 수 있도록 각 예측 결과를 파라미터 딕셔너리로 변환한다.
        payload = [
            {
                "m": p["member_id"],
                "cp": p["churn_probability"],
                "rl": p["risk_level"],
                "tf": json.dumps(
                    p["top_features"],
                    ensure_ascii=False,
                ),
                "v": CHURN_MODEL_VERSION,
            }
            for p in predictions
        ]

        self.db.execute(
            text(
                """
                INSERT INTO ai.churn_predictions
                       (member_id, churn_probability, risk_level, top_features,
                        model_version, predicted_at)
                VALUES (:m, :cp, :rl, CAST(:tf AS jsonb), :v, now())

                -- 회원별 기존 예측 결과가 있으면 새 결과로 갱신한다.
                ON CONFLICT (member_id) DO UPDATE
                   SET churn_probability = EXCLUDED.churn_probability,
                       risk_level = EXCLUDED.risk_level,
                       top_features = EXCLUDED.top_features,
                       model_version = EXCLUDED.model_version,
                       predicted_at = now()
                """
            ),
            payload,
        )

        self.db.commit()
        logger.info("이탈 예측 저장: %d명", len(payload))
        return len(payload)

    # ------------------------------------------------------------------ 조회
    def risk_summary(self) -> Dict[str, int]:
        """저장된 예측 결과에서 위험 등급별 회원 수를 센다."""
        rows = self.db.execute(
            text(
                """
                SELECT risk_level, COUNT(*)::int
                  FROM ai.churn_predictions
                 GROUP BY risk_level
                """
            )
        ).all()

        # 데이터가 없는 위험 등급도 0으로 반환하도록 기본값을 준비한다.
        summary = {"HIGH": 0, "MID": 0, "LOW": 0}

        # 데이터베이스에서 조회한 건수로 기본값을 갱신한다.
        for level, count in rows:
            summary[level] = int(count)

        return summary

    def list_risk_members(
        self,
        risk_level: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict]:
        """위험 회원 목록을 조회한다.

        risk_level을 지정하면 해당 위험 등급만 조회하고,
        limit과 offset으로 페이지 단위 조회를 한다.
        """
        # 기본적으로 모든 위험 등급을 조회하도록 조건을 시작한다.
        where = "WHERE 1=1"
        params: Dict = {"lim": limit, "off": offset}

        # 위험 등급이 전달되면 SQL 조건과 파라미터에 추가한다.
        if risk_level:
            where += " AND c.risk_level = :rl"
            params["rl"] = risk_level

        rows = self.db.execute(
            text(
                f"""
                SELECT c.member_id, m.name, m.email, g.grade_name,
                       c.churn_probability::float, c.risk_level, c.top_features,
                       COALESCE(s.recency_days, 999) AS recency_days,
                       m.order_count, m.total_paid::float
                  FROM ai.churn_predictions c
                  JOIN shop.members m ON m.member_id = c.member_id
                  JOIN shop.member_grades g ON g.grade_id = m.grade_id
                  LEFT JOIN ai.customer_segments s ON s.member_id = c.member_id
                  {where}
                 ORDER BY c.churn_probability DESC
                 LIMIT :lim OFFSET :off
                """
            ),
            params,
        ).mappings().all()

        def mask(email: str) -> str:
            """화면에 표시할 이메일에서 일부 문자를 별표로 가린다."""
            local, _, domain = (email or "").partition("@")

            # 아이디 부분이 짧으면 전체 아이디를 보여 주지 않는다.
            if len(local) <= 2:
                return f"{local}***@{domain}"

            # 아이디 앞 두 글자만 남기고 나머지는 별표로 바꾼다.
            return f"{local[:2]}{'*' * (len(local) - 2)}@{domain}"

        # 데이터베이스 결과를 화면/API에서 사용할 형태로 정리한다.
        return [
            {
                "member_id": int(r["member_id"]),
                "name": r["name"],
                "email_masked": mask(r["email"]),
                "grade_name": r["grade_name"],
                "churn_probability": float(r["churn_probability"]),
                "risk_level": r["risk_level"],
                "recency_days": int(r["recency_days"]),
                "order_count": int(r["order_count"] or 0),
                "total_paid": float(r["total_paid"] or 0),
                "top_features": r["top_features"],
            }
            for r in rows
        ]

    def last_predicted_at(self) -> Optional[datetime]:
        """가장 최근에 이탈 예측을 저장한 시간을 반환한다."""
        row = self.db.execute(
            text(
                "SELECT MAX(predicted_at) FROM ai.churn_predictions"
            )
        ).first()

        # 예측 기록이 있으면 가장 늦은 시간을, 없으면 None을 반환한다.
        return row[0] if row else None