"""협업 필터링 기반 도서 추천 엔진.

아이템 기반 추천, 사용자 기반 추천, 함께 구매한 도서 분석을 제공한다.
사용자가 본 도서, 구매한 도서, 위시리스트, 리뷰 평점을 추천에 활용한다.
"""
import logging
import math
import os
import pickle
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from team_backend.app.core.config import settings

logger = logging.getLogger(__name__)

# 사용자의 행동을 추천 계산에 반영할 때 사용할 기본 가중치
W_ORDER = 5.0       # 구매
W_WISHLIST = 3.0    # 위시리스트 추가
W_VIEW = 1.0        # 도서 상세 조회

# 모델 버전이 바뀌었는지 확인할 때 사용하는 이름
MODEL_VERSION = "cf-v1"


# -----------------------------------------------------------------------------
# 데이터 구조
# -----------------------------------------------------------------------------
@dataclass
class InteractionMatrix:
    """회원과 도서 사이의 상호작용 점수를 희소 행렬 형태로 저장한다."""

    # 회원 번호를 기준으로 어떤 도서와 상호작용했는지 저장한다.
    # 예: user_items[회원 번호][도서 번호] = 점수
    user_items: Dict[int, Dict[int, float]] = field(
        default_factory=lambda: defaultdict(dict)
    )

    # 도서 번호를 기준으로 어떤 회원이 상호작용했는지 저장한다.
    # 예: item_users[도서 번호][회원 번호] = 점수
    item_users: Dict[int, Dict[int, float]] = field(
        default_factory=lambda: defaultdict(dict)
    )

    def add(
        self,
        member_id: int,
        book_id: int,
        weight: float,
    ) -> None:
        """회원과 도서 사이의 점수를 더한다."""

        # 같은 회원이 같은 도서와 여러 번 상호작용하면 점수를 누적한다.
        current = self.user_items[member_id].get(book_id, 0.0)
        value = current + weight

        # 회원 기준과 도서 기준 데이터에 같은 점수를 기록한다.
        self.user_items[member_id][book_id] = value
        self.item_users[book_id][member_id] = value

    @property
    def user_count(self) -> int:
        """상호작용 기록이 있는 회원 수."""
        return len(self.user_items)

    @property
    def item_count(self) -> int:
        """상호작용 기록이 있는 도서 수."""
        return len(self.item_users)

    @property
    def interaction_count(self) -> int:
        """회원-도서 조합의 총 개수."""
        return sum(
            len(items)
            for items in self.user_items.values()
        )


# -----------------------------------------------------------------------------
# 추천 엔진
# -----------------------------------------------------------------------------
class CollaborativeFilteringRecommender:
    """상호작용 데이터로 도서를 추천하는 엔진."""

    def __init__(self, db: Session):
        self.db = db

        # DB에서 가져온 회원-도서 점수표
        self.matrix = InteractionMatrix()

        # 각 도서와 비슷한 도서 목록
        # 예: {도서 번호: [(비슷한 도서 번호, 유사도 점수), ...]}
        self.item_similarity: Dict[int, List[Tuple[int, float]]] = {}

        # 코사인 유사도 계산에 필요한 각 도서 벡터의 크기
        self.item_norms: Dict[int, float] = {}

        # 추천할 데이터가 부족할 때 사용할 인기 도서 목록
        self.popular: List[Tuple[int, float]] = []

        # 카테고리, 판매량, 평점 등 추천 보정에 사용하는 도서 정보
        self.book_meta: Dict[int, dict] = {}

        # 모델이 마지막으로 학습된 시각
        self.trained_at: Optional[datetime] = None

    # ------------------------------------------------------------------ 데이터 적재
    def load_interactions(self) -> InteractionMatrix:
        """DB에서 구매·리뷰·위시리스트·조회 이력을 가져온다."""

        matrix = InteractionMatrix()

        # 1) 구매 이력은 추천에 가장 큰 영향을 주는 행동으로 취급한다.
        rows = self.db.execute(
            text(
                "SELECT member_id, book_id, qty "
                "FROM ai.v_order_matrix"
            )
        ).all()

        for member_id, book_id, qty in rows:
            # 한 주문에서 같은 도서를 많이 샀더라도 가중치는 최대 3개까지만 반영한다.
            weight = W_ORDER * min(float(qty), 3.0)
            matrix.add(
                int(member_id),
                int(book_id),
                weight,
            )

        # 2) 블라인드 처리되지 않은 리뷰의 평균 평점을 가져온다.
        rows = self.db.execute(
            text(
                """
                SELECT member_id, book_id, AVG(rating)::float
                FROM shop.reviews
                WHERE is_blinded = false
                GROUP BY member_id, book_id
                """
            )
        ).all()

        for member_id, book_id, rating in rows:
            # 리뷰 평점을 그대로 상호작용 점수로 사용한다.
            matrix.add(
                int(member_id),
                int(book_id),
                float(rating),
            )

        # 3) 위시리스트에 담긴 도서를 가져온다.
        rows = self.db.execute(
            text(
                "SELECT member_id, book_id "
                "FROM shop.wishlists"
            )
        ).all()

        for member_id, book_id in rows:
            matrix.add(
                int(member_id),
                int(book_id),
                W_WISHLIST,
            )

        # 4) 최근 90일 안에 상세 페이지를 본 기록을 가져온다.
        rows = self.db.execute(
            text(
                """
                SELECT member_id, book_id, COUNT(*)
                FROM log.recent_views
                WHERE member_id IS NOT NULL
                  AND created_at >= now() - interval '90 days'
                GROUP BY member_id, book_id
                """
            )
        ).all()

        for member_id, book_id, count in rows:
            # 같은 책을 여러 번 봐도 조회 가중치는 최대 3회분까지만 반영한다.
            weight = W_VIEW * min(float(count), 3.0)
            matrix.add(
                int(member_id),
                int(book_id),
                weight,
            )

        # 새로 만든 상호작용 행렬을 추천기 객체에 저장한다.
        self.matrix = matrix

        logger.info(
            "상호작용 적재 완료: 사용자 %d, 도서 %d, 상호작용 %d",
            matrix.user_count,
            matrix.item_count,
            matrix.interaction_count,
        )
        return matrix

    def load_book_meta(self) -> Dict[int, dict]:
        """추천에 필요한 도서 정보와 판매 가능 상태를 적재한다."""

        rows = self.db.execute(
            text(
                """
                SELECT b.book_id,
                       b.category_id,
                       b.sales_count,
                       b.rating_avg,
                       b.status::text,
                       COALESCE(b.sentiment_score, 0)::float
                FROM shop.books b
                WHERE b.status IN ('SALE', 'PREORDER')
                """
            )
        ).all()

        # 도서 번호를 키로 사용하면 추천 결과를 보정할 때 정보를 빠르게 찾을 수 있다.
        self.book_meta = {
            int(row[0]): {
                "category_id": row[1],
                "sales_count": int(row[2] or 0),
                "rating_avg": float(row[3] or 0),
                "status": row[4],
                "sentiment": float(row[5] or 0),
            }
            for row in rows
        }

        return self.book_meta

    # ------------------------------------------------------------------ 모델 학습
    def fit(self, top_k: Optional[int] = None) -> dict:
        """도서끼리 얼마나 비슷한지 코사인 유사도를 계산한다."""

        # 설정에 별도 값이 없으면 기본 이웃 수를 사용한다.
        top_k = top_k or settings.CF_NEIGHBOR_K

        # 아직 데이터를 적재하지 않았으면 DB에서 가져온다.
        if not self.matrix.item_users:
            self.load_interactions()

        if not self.book_meta:
            self.load_book_meta()

        # 각 도서의 벡터 크기(노름)를 계산한다.
        # 이 값은 코사인 유사도 계산의 분모로 사용된다.
        self.item_norms = {
            item: math.sqrt(
                sum(value * value for value in users.values())
            )
            for item, users in self.matrix.item_users.items()
        }

        # 두 도서에 모두 상호작용한 회원이 있을 때만 도서 쌍의 점수를 계산한다.
        dot: Dict[int, Dict[int, float]] = defaultdict(
            lambda: defaultdict(float)
        )

        for user, items in self.matrix.user_items.items():
            entries = list(items.items())

            # 한 회원이 상호작용한 도서가 너무 적거나 많으면 쌍 계산에서 제외한다.
            if len(entries) < 2 or len(entries) > 500:
                continue

            # 회원이 상호작용한 도서 쌍마다 점수의 곱을 누적한다.
            for i in range(len(entries)):
                book_i, weight_i = entries[i]

                for j in range(i + 1, len(entries)):
                    book_j, weight_j = entries[j]
                    product = weight_i * weight_j

                    # 도서 쌍은 어느 방향에서 조회해도 찾을 수 있게 양쪽에 저장한다.
                    dot[book_i][book_j] += product
                    dot[book_j][book_i] += product

        similarity: Dict[int, List[Tuple[int, float]]] = {}

        # 누적 점수를 코사인 유사도로 바꾸고, 도서별 상위 이웃만 저장한다.
        for item, partners in dot.items():
            norm_i = self.item_norms.get(item, 0.0)

            # 벡터 크기가 0이면 나눗셈할 수 없으므로 건너뛴다.
            if norm_i == 0:
                continue

            scored = []

            for other, product in partners.items():
                norm_j = self.item_norms.get(other, 0.0)

                if norm_j == 0:
                    continue

                # 코사인 유사도: 두 벡터의 내적을 각 벡터 크기의 곱으로 나눈다.
                sim = product / (norm_i * norm_j)

                # 아주 낮은 유사도는 추천에 쓰지 않는다.
                if sim > 0.01:
                    scored.append((other, round(sim, 5)))

            # 유사도가 높은 도서부터 정렬하고 상위 top_k개만 보관한다.
            scored.sort(
                key=lambda item_score: item_score[1],
                reverse=True,
            )
            similarity[item] = scored[:top_k]

        self.item_similarity = similarity

        # 추천 데이터가 부족할 때 사용할 인기 도서 목록도 함께 만든다.
        self.popular = sorted(
            (
                (
                    book_id,
                    meta["sales_count"] * 1.0
                    + meta["rating_avg"] * 10,
                )
                for book_id, meta in self.book_meta.items()
            ),
            key=lambda item_score: item_score[1],
            reverse=True,
        )[:100]

        self.trained_at = datetime.now(timezone.utc)

        # 학습 결과를 숫자로 요약해 반환한다.
        metrics = {
            "users": self.matrix.user_count,
            "items": self.matrix.item_count,
            "interactions": self.matrix.interaction_count,
            "similar_pairs": sum(
                len(items)
                for items in similarity.values()
            ),
            "coverage": round(
                len(similarity) / max(self.matrix.item_count, 1),
                4,
            ),
        }

        logger.info("아이템 유사도 학습 완료: %s", metrics)
        return metrics

    # ------------------------------------------------------------------ 회원별 추천
    def recommend_for_member(
        self,
        member_id: int,
        top_n: Optional[int] = None,
        exclude_purchased: bool = True,
    ) -> List[Tuple[int, float, str]]:
        """회원에게 추천할 도서 번호, 점수, 추천 이유를 반환한다."""

        top_n = top_n or settings.CF_TOP_N

        # 아직 도서 유사도를 계산하지 않았다면 먼저 학습한다.
        if not self.item_similarity:
            self.fit()

        # 이 회원이 구매·조회·찜한 도서와 각 상호작용 점수를 가져온다.
        profile = self.matrix.user_items.get(member_id, {})

        # 상호작용 기록이 적으면 개인화 대신 인기 도서 추천으로 대체한다.
        if len(profile) < settings.CF_MIN_INTERACTIONS:
            return self._cold_start(member_id, top_n)

        scores: Dict[int, float] = defaultdict(float)
        source: Dict[int, int] = {}

        # 회원이 관심을 보인 도서와 비슷한 도서에 추천 점수를 더한다.
        for book_id, weight in profile.items():
            for similar_id, similarity_score in self.item_similarity.get(
                book_id,
                [],
            ):
                # 이미 상호작용한 도서는 추천에서 제외할 수 있다.
                if exclude_purchased and similar_id in profile:
                    continue

                # 현재 판매 가능한 도서 정보가 없으면 추천하지 않는다.
                meta = self.book_meta.get(similar_id)
                if meta is None:
                    continue

                # 유사도가 높고 회원의 관심 점수가 클수록 추천 점수가 커진다.
                contribution = similarity_score * weight
                scores[similar_id] += contribution

                # 추천 점수에 가장 크게 기여한 도서를 추천 이유로 기록한다.
                if contribution > scores.get(similar_id, 0) * 0.5:
                    source[similar_id] = book_id

        # 점수가 만들어지지 않았으면 인기 도서 추천으로 대체한다.
        if not scores:
            return self._cold_start(member_id, top_n)

        # 회원이 선호하는 카테고리를 계산해 같은 카테고리 도서 점수를 높인다.
        category_pref = self._category_preference(profile)

        for book_id in list(scores.keys()):
            meta = self.book_meta.get(book_id, {})
            category_id = meta.get("category_id")

            # 선호 카테고리에 해당하면 카테고리 선호도만큼 점수를 보정한다.
            if category_id in category_pref:
                scores[book_id] *= (
                    1.0 + 0.15 * category_pref[category_id]
                )

            # 평점이 높은 도서에 작은 추가 가중치를 준다.
            scores[book_id] *= (
                1.0 + 0.02 * meta.get("rating_avg", 0)
            )

        # 추천 점수가 높은 순서로 정렬하고 필요한 개수만 고른다.
        ranked = sorted(
            scores.items(),
            key=lambda item_score: item_score[1],
            reverse=True,
        )[:top_n]

        result = []

        for book_id, score in ranked:
            source_book_id = source.get(book_id)

            # 기본 추천 이유
            reason = "구매 이력이 비슷한 회원들이 함께 선택한 도서"

            # 어떤 도서가 추천 점수에 기여했는지 알면 이유에 제목을 넣는다.
            if source_book_id is not None:
                title = self._book_title(source_book_id)
                if title:
                    reason = f"'{title}'을(를) 보신 분들이 함께 본 도서"

            result.append(
                (
                    book_id,
                    round(score, 5),
                    reason,
                )
            )

        return result

    def _category_preference(
        self,
        profile: Dict[int, float],
    ) -> Dict[int, float]:
        """회원의 상호작용 점수를 카테고리별 선호 비율로 바꾼다."""

        counter: Dict[int, float] = defaultdict(float)

        # 회원이 상호작용한 도서들의 점수를 카테고리별로 합산한다.
        for book_id, weight in profile.items():
            category_id = self.book_meta.get(
                book_id,
                {},
            ).get("category_id")

            if category_id:
                counter[category_id] += weight

        # 전체 점수로 나눠 각 카테고리의 비율을 계산한다.
        # 점수가 0일 때 나눗셈 오류가 나지 않도록 1.0을 사용한다.
        total = sum(counter.values()) or 1.0

        return {
            category_id: value / total
            for category_id, value in counter.items()
        }

    def _book_title(self, book_id: int) -> Optional[str]:
        """도서 번호로 도서 제목을 조회한다."""

        row = self.db.execute(
            text(
                "SELECT title FROM shop.books "
                "WHERE book_id = :bid"
            ),
            {"bid": book_id},
        ).first()

        return row[0] if row else None

    def _cold_start(
        self,
        member_id: Optional[int],
        top_n: int,
    ) -> List[Tuple[int, float, str]]:
        """개인화 데이터가 부족한 회원에게 인기 도서를 추천한다."""

        # 인기 목록이 아직 없으면 도서 정보를 불러와 판매량과 평점으로 정렬한다.
        if not self.popular:
            self.load_book_meta()
            self.popular = sorted(
                (
                    (
                        book_id,
                        meta["sales_count"] * 1.0
                        + meta["rating_avg"] * 10,
                    )
                    for book_id, meta in self.book_meta.items()
                ),
                key=lambda item_score: item_score[1],
                reverse=True,
            )[:100]

        # 회원이 이미 상호작용한 도서는 인기 추천에서도 제외한다.
        owned = (
            self.matrix.user_items.get(member_id, {})
            if member_id
            else {}
        )

        result = []

        for book_id, score in self.popular:
            if book_id in owned:
                continue

            # 원래 점수를 100으로 나눠 추천 점수로 반환한다.
            result.append(
                (
                    book_id,
                    round(score / 100.0, 5),
                    "지금 많이 찾는 인기 도서",
                )
            )

            if len(result) >= top_n:
                break

        return result

    def similar_books(
        self,
        book_id: int,
        top_n: int = 10,
    ) -> List[Tuple[int, float]]:
        """특정 도서와 비슷한 도서 번호와 유사도 점수를 반환한다."""

        # 아직 학습되지 않았다면 도서 유사도를 먼저 계산한다.
        if not self.item_similarity:
            self.fit()

        items = self.item_similarity.get(book_id, [])

        # 협업 필터링 유사도가 있으면 해당 결과를 사용한다.
        if items:
            return items[:top_n]

        # 유사도 데이터가 없으면 카테고리·저자·평점으로 대체 검색한다.
        return self._similar_by_content(book_id, top_n)

    def _similar_by_content(
        self,
        book_id: int,
        top_n: int,
    ) -> List[Tuple[int, float]]:
        """같은 카테고리나 저자 도서를 찾아 유사 도서로 반환한다."""

        # 기준 도서와 카테고리가 같거나 저자가 겹치는 도서를 찾는다.
        rows = self.db.execute(
            text(
                """
                WITH target AS (
                    SELECT category_id
                    FROM shop.books
                    WHERE book_id = :bid
                )
                SELECT b.book_id,
                       (
                           CASE
                               WHEN b.category_id =
                                    (SELECT category_id FROM target)
                               THEN 0.6
                               ELSE 0.2
                           END
                           + LEAST(b.rating_avg / 10.0, 0.5)
                       )::float AS score
                FROM shop.books b
                WHERE b.book_id <> :bid
                  AND b.status = 'SALE'
                  AND (
                      b.category_id =
                          (SELECT category_id FROM target)
                      OR b.book_id IN (
                          SELECT ba2.book_id
                          FROM shop.book_authors ba2
                          WHERE ba2.author_id IN (
                              SELECT author_id
                              FROM shop.book_authors
                              WHERE book_id = :bid
                          )
                      )
                  )
                ORDER BY score DESC, b.sales_count DESC
                LIMIT :lim
                """
            ),
            {
                "bid": book_id,
                "lim": top_n,
            },
        ).all()

        return [
            (int(row[0]), round(float(row[1]), 5))
            for row in rows
        ]

    def user_based_recommend(
        self,
        member_id: int,
        top_n: int = 10,
        neighbor_k: Optional[int] = None,
    ) -> List[Tuple[int, float, str]]:
        """취향이 비슷한 회원들이 선호한 도서를 추천한다."""

        neighbor_k = neighbor_k or settings.CF_NEIGHBOR_K

        # 사용자-도서 상호작용 자료가 없으면 DB에서 적재한다.
        if not self.matrix.user_items:
            self.load_interactions()
            self.load_book_meta()

        profile = self.matrix.user_items.get(member_id)

        # 상호작용 기록이 없는 회원은 인기 도서 추천을 사용한다.
        if not profile:
            return self._cold_start(member_id, top_n)

        # 현재 회원의 상호작용 벡터 크기를 계산한다.
        norm_me = math.sqrt(
            sum(value * value for value in profile.values())
        ) or 1.0

        similarities: List[Tuple[int, float]] = []

        # 현재 회원과 같은 도서에 상호작용한 회원만 비교 대상으로 삼는다.
        candidate_users = set()
        for book_id in profile:
            candidate_users.update(
                self.matrix.item_users.get(book_id, {}).keys()
            )

        # 현재 회원 자신은 이웃 목록에서 제외한다.
        candidate_users.discard(member_id)

        for other in candidate_users:
            other_profile = self.matrix.user_items.get(other, {})

            # 두 회원이 공통으로 본 도서 점수의 내적을 계산한다.
            dot = sum(
                weight * other_profile.get(book_id, 0.0)
                for book_id, weight in profile.items()
            )

            # 공통 선호 점수가 없거나 음수면 유사 이웃으로 쓰지 않는다.
            if dot <= 0:
                continue

            norm_other = math.sqrt(
                sum(value * value for value in other_profile.values())
            ) or 1.0

            # 현재 회원과 다른 회원의 코사인 유사도를 계산한다.
            similarities.append(
                (other, dot / (norm_me * norm_other))
            )

        # 유사한 회원부터 정렬해 상위 이웃만 선택한다.
        similarities.sort(
            key=lambda item_score: item_score[1],
            reverse=True,
        )
        neighbors = similarities[:neighbor_k]

        scores: Dict[int, float] = defaultdict(float)

        # 이웃 회원이 선호했지만 현재 회원은 아직 보지 않은 도서에 점수를 준다.
        for other, similarity_score in neighbors:
            other_profile = self.matrix.user_items.get(other, {})

            for book_id, weight in other_profile.items():
                if book_id in profile:
                    continue

                # 판매 가능한 도서 정보가 없는 항목은 추천에서 제외한다.
                if book_id not in self.book_meta:
                    continue

                scores[book_id] += similarity_score * weight

        # 점수가 높은 도서부터 정렬해 top_n개만 반환한다.
        ranked = sorted(
            scores.items(),
            key=lambda item_score: item_score[1],
            reverse=True,
        )[:top_n]

        return [
            (
                book_id,
                round(score, 5),
                "취향이 비슷한 회원이 선택한 도서",
            )
            for book_id, score in ranked
        ]

    # ------------------------------------------------------------------ 결과 저장
    def persist(
        self,
        member_ids: Optional[List[int]] = None,
        top_n: Optional[int] = None,
    ) -> int:
        """도서 유사도와 회원별 추천 결과를 DB에 저장한다."""

        top_n = top_n or settings.CF_TOP_N

        # 회원 번호 목록이 전달되지 않으면 상호작용 기록이 있는 모든 회원을 대상으로 한다.
        targets = member_ids or list(self.matrix.user_items.keys())

        # 기존 COSINE 유사도 결과를 지우고 새 결과를 넣는다.
        self.db.execute(
            text(
                "DELETE FROM ai.book_similarities "
                "WHERE algorithm = 'COSINE'"
            )
        )

        sim_rows = []

        # 도서별 상위 유사 도서 20개를 DB 입력용 데이터로 만든다.
        for book_id, partners in self.item_similarity.items():
            for other, similarity_score in partners[:20]:
                sim_rows.append(
                    {
                        "b": book_id,
                        "s": other,
                        "sim": similarity_score,
                    }
                )

        if sim_rows:
            self.db.execute(
                text(
                    """
                    INSERT INTO ai.book_similarities(
                        book_id,
                        similar_book_id,
                        similarity,
                        algorithm
                    )
                    VALUES (:b, :s, :sim, 'COSINE')
                    ON CONFLICT (
                        book_id,
                        similar_book_id,
                        algorithm
                    )
                    DO UPDATE SET
                        similarity = EXCLUDED.similarity,
                        updated_at = now()
                    """
                ),
                sim_rows,
            )

        # 기존 ITEM_CF 회원 추천 결과를 지우고 새 결과를 넣는다.
        self.db.execute(
            text(
                "DELETE FROM ai.recommendations "
                "WHERE algorithm = 'ITEM_CF'"
            )
        )

        rec_rows = []

        for member_id in targets:
            # 회원별 추천 목록을 순위와 함께 저장할 데이터로 바꾼다.
            recommendations = self.recommend_for_member(
                member_id,
                top_n,
            )

            for rank, (book_id, score, _reason) in enumerate(
                recommendations,
                start=1,
            ):
                rec_rows.append(
                    {
                        "m": member_id,
                        "b": book_id,
                        "sc": score,
                        "r": rank,
                        "v": MODEL_VERSION,
                    }
                )

        if rec_rows:
            self.db.execute(
                text(
                    """
                    INSERT INTO ai.recommendations(
                        member_id,
                        book_id,
                        score,
                        algorithm,
                        rank,
                        model_version
                    )
                    VALUES (:m, :b, :sc, 'ITEM_CF', :r, :v)
                    ON CONFLICT (
                        member_id,
                        book_id,
                        algorithm
                    )
                    DO UPDATE SET
                        score = EXCLUDED.score,
                        rank = EXCLUDED.rank,
                        created_at = now()
                    """
                ),
                rec_rows,
            )

        # 유사도와 추천 결과를 모두 DB에 저장한다.
        self.db.commit()

        logger.info(
            "추천 결과 저장: 회원 %d명, %d건",
            len(targets),
            len(rec_rows),
        )
        return len(rec_rows)

    def save_artifact(
        self,
        path: Optional[str] = None,
    ) -> str:
        """학습한 추천 모델의 일부 데이터를 파일로 저장한다."""

        # 경로가 전달되지 않으면 설정된 모델 저장 폴더를 사용한다.
        path = path or os.path.join(
            settings.AI_MODEL_DIR,
            "cf_item_similarity.pkl",
        )

        # 저장 폴더가 없으면 새로 만든다.
        os.makedirs(os.path.dirname(path), exist_ok=True)

        # pickle로 버전, 학습 시각, 유사도, 인기 목록을 저장한다.
        with open(path, "wb") as fp:
            pickle.dump(
                {
                    "version": MODEL_VERSION,
                    "trained_at": self.trained_at,
                    "item_similarity": self.item_similarity,
                    "popular": self.popular,
                },
                fp,
            )

        return path

    def load_artifact(
        self,
        path: Optional[str] = None,
    ) -> bool:
        """파일로 저장해 둔 추천 모델 데이터를 불러온다."""

        path = path or os.path.join(
            settings.AI_MODEL_DIR,
            "cf_item_similarity.pkl",
        )

        # 저장된 파일이 없으면 불러오지 못했다고 알린다.
        if not os.path.exists(path):
            return False

        with open(path, "rb") as fp:
            data = pickle.load(fp)

        # 파일에 저장된 추천 데이터와 학습 시각을 객체에 복원한다.
        self.item_similarity = data.get("item_similarity", {})
        self.popular = data.get("popular", [])
        self.trained_at = data.get("trained_at")

        return True


# -----------------------------------------------------------------------------
# 연관 규칙: 함께 구매한 도서 분석
# -----------------------------------------------------------------------------
class AssociationRuleMiner:
    """한 주문에서 함께 구매된 도서 조합을 분석한다."""

    def __init__(self, db: Session):
        self.db = db

    def mine(
        self,
        min_support: float = 0.001,
        min_confidence: float = 0.05,
    ) -> List[dict]:
        """주문 데이터에서 지지도, 신뢰도, 향상도를 계산한다."""

        # 결제가 완료됐거나 배송·구매 확정 단계인 주문의 도서를 가져온다.
        rows = self.db.execute(
            text(
                """
                SELECT o.order_id, oi.book_id
                FROM shop.orders o
                JOIN shop.order_items oi
                  ON oi.order_id = o.order_id
                WHERE o.status IN (
                    'PAID',
                    'PREPARING',
                    'SHIPPING',
                    'DELIVERED',
                    'CONFIRMED'
                )
                """
            )
        ).all()

        # 주문 번호별로 구매한 도서 번호를 묶는다.
        baskets: Dict[int, set] = defaultdict(set)
        for order_id, book_id in rows:
            baskets[int(order_id)].add(int(book_id))

        total_orders = len(baskets)

        # 분석할 주문이 없으면 규칙도 만들 수 없다.
        if total_orders == 0:
            return []

        # 각 도서가 포함된 주문 수와 도서 쌍이 함께 나온 주문 수를 센다.
        item_count: Dict[int, int] = defaultdict(int)
        pair_count: Dict[Tuple[int, int], int] = defaultdict(int)

        for items in baskets.values():
            sorted_items = sorted(items)

            # 각 도서가 주문에 등장한 횟수를 집계한다.
            for item in sorted_items:
                item_count[item] += 1

            # 같은 주문에 들어 있는 모든 방향의 도서 쌍을 집계한다.
            for i in range(len(sorted_items)):
                for j in range(len(sorted_items)):
                    if i == j:
                        continue

                    pair_count[
                        (sorted_items[i], sorted_items[j])
                    ] += 1

        rules = []

        for (ante, cons), count in pair_count.items():
            # 지지도: 전체 주문 중 두 도서가 함께 포함된 비율
            support = count / total_orders

            # 너무 드물게 나타나는 조합은 제외한다.
            if support < min_support:
                continue

            # 신뢰도: ante 도서를 산 주문 중 cons 도서도 산 비율
            confidence = count / item_count[ante]

            # 신뢰도가 기준보다 낮은 규칙은 제외한다.
            if confidence < min_confidence:
                continue

            # cons 도서가 전체 주문에서 나온 비율
            cons_support = item_count[cons] / total_orders

            # 향상도: cons 도서가 일반적으로 팔리는 정도보다
            # ante 도서와 함께 있을 때 얼마나 더 자주 팔리는지 나타낸다.
            lift = (
                confidence / cons_support
                if cons_support
                else 0.0
            )

            rules.append(
                {
                    "antecedent": ante,
                    "consequent": cons,
                    "support": round(support, 6),
                    "confidence": round(confidence, 6),
                    "lift": round(lift, 4),
                    "pair_count": count,
                }
            )

        # 향상도와 신뢰도가 높은 규칙부터 정렬한다.
        rules.sort(
            key=lambda rule: (
                rule["lift"],
                rule["confidence"],
            ),
            reverse=True,
        )

        logger.info(
            "연관 규칙 추출: 주문 %d건, 규칙 %d개",
            total_orders,
            len(rules),
        )
        return rules

    def persist(
        self,
        rules: List[dict],
        limit: int = 2000,
    ) -> int:
        """계산한 연관 규칙을 DB에 저장한다."""

        # 이전 규칙을 지운 후 새 분석 결과로 교체한다.
        self.db.execute(
            text("DELETE FROM ai.association_rules")
        )

        # 새 규칙이 없으면 삭제 사항만 저장하고 종료한다.
        if not rules:
            self.db.commit()
            return 0

        # 최대 limit개 규칙을 테이블에 저장한다.
        self.db.execute(
            text(
                """
                INSERT INTO ai.association_rules(
                    antecedent,
                    consequent,
                    support,
                    confidence,
                    lift,
                    pair_count
                )
                VALUES (
                    :antecedent,
                    :consequent,
                    :support,
                    :confidence,
                    :lift,
                    :pair_count
                )
                ON CONFLICT (antecedent, consequent)
                DO UPDATE SET
                    support = EXCLUDED.support,
                    confidence = EXCLUDED.confidence,
                    lift = EXCLUDED.lift,
                    pair_count = EXCLUDED.pair_count,
                    updated_at = now()
                """
            ),
            rules[:limit],
        )

        self.db.commit()

        # 실제로 저장한 규칙 수를 반환한다.
        return min(len(rules), limit)

    def frequently_bought_together(
        self,
        book_id: int,
        top_n: int = 6,
    ) -> List[Tuple[int, float]]:
        """특정 도서와 함께 자주 구매된 도서와 향상도를 반환한다."""

        rows = self.db.execute(
            text(
                """
                SELECT consequent, lift
                FROM ai.association_rules
                WHERE antecedent = :bid
                ORDER BY lift DESC, confidence DESC
                LIMIT :lim
                """
            ),
            {
                "bid": book_id,
                "lim": top_n,
            },
        ).all()

        return [
            (int(row[0]), float(row[1]))
            for row in rows
        ]


# -----------------------------------------------------------------------------
# 추천기 캐시
# -----------------------------------------------------------------------------
# 같은 프로세스 안에서 학습한 추천기를 재사용해 매 요청마다 다시 만들지 않는다.
_recommender_cache: Dict[
    str,
    CollaborativeFilteringRecommender,
] = {}


def get_recommender(
    db: Session,
    force_reload: bool = False,
) -> CollaborativeFilteringRecommender:
    """캐시된 추천기를 반환하거나 새 추천기를 준비한다."""

    cached = _recommender_cache.get("default")

    if cached is not None and not force_reload:
        # 캐시된 추천기를 사용하되 현재 요청의 DB 세션으로 바꿔 준다.
        cached.db = db
        return cached

    # 캐시가 없거나 강제 갱신을 요청하면 추천기를 새로 만든다.
    recommender = CollaborativeFilteringRecommender(db)
    recommender.load_interactions()
    recommender.load_book_meta()

    # 학습 결과 파일이 있으면 불러오고, 없으면 새로 유사도를 계산한다.
    if not recommender.load_artifact():
        recommender.fit()

    _recommender_cache["default"] = recommender
    return recommender


def invalidate_recommender() -> None:
    """캐시를 비워 다음 요청에서 추천기를 다시 준비하게 한다."""

    _recommender_cache.pop("default", None)