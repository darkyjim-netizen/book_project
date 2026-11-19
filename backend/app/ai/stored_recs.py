"""AI 배치(ai/recommend_batch.py)가 저장해 둔 추천을 읽는다.

backend/app/ai/stored_recs.py 로 복사해서 쓴다. 모델을 직접 돌리지 않고
ai.recommendations 테이블만 읽기 때문에 PyTorch 가 필요 없고 응답이 빠르다.
"""
from typing import List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

REASONS = {
    "SASREC": "회원님의 구매 흐름을 분석한 맞춤 추천",
    "POPULAR": "많은 분들이 구매한 인기 도서",
}


def stored_recommendations(
    db: Session, member_id: int, limit: int
) -> Tuple[List[Tuple[int, float, str]], Optional[str]]:
    """(도서번호, 점수, 이유) 목록과 사용된 알고리즘 이름을 돌려준다.

    저장된 추천이 없는 회원(새로 가입한 회원 등)이면 ([], None) 을 돌려주므로,
    호출하는 쪽에서 기존 인기도서 로직으로 대체하면 된다.
    """
    rows = db.execute(
        text(
            """
            SELECT r.book_id, r.score, r.algorithm
            FROM ai.recommendations r
            JOIN shop.books b ON b.book_id = r.book_id
            WHERE r.member_id = :member_id
              AND r.algorithm IN ('SASREC', 'POPULAR')
              AND b.status::text = 'SALE'
            ORDER BY r.rank
            LIMIT :limit
            """
        ),
        {"member_id": member_id, "limit": limit},
    ).all()
    if not rows:
        return [], None
    triples = [(int(b), float(s), REASONS.get(a, "")) for b, s, a in rows]
    algorithm = "SASREC" if any(a == "SASREC" for _, _, a in rows) else "POPULAR"
    return triples, algorithm