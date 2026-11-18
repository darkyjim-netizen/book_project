"""SASRec 추천 배치: 회원별 추천 5권을 계산해 ai.recommendations 에 저장한다.

실행 (backend 폴더에서):
    python scripts/recommend_batch.py --dry     # 계산만 하고 저장하지 않음
    python scripts/recommend_batch.py           # 계산 후 DB에 저장

- 구매 이력이 있는 회원: SASRec 모델로 추천 (algorithm = SASREC)
- 구매 이력이 없는 회원: 인기 도서 (algorithm = POPULAR)
- 저장된 결과는 API(GET /ai/recommendations)가 읽어서 보여 준다.
- 새 주문이 쌓이면 이 스크립트를 다시 실행해 추천을 갱신한다.
- DB 접속 정보는 backend/.env 의 DB_* 값을 쓴다 (DATABASE_URL 환경변수가 있으면 그 값 우선).
"""
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import torch
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.ai.sasrec.model import SASRec  # noqa: E402

CKPT = BACKEND_DIR / "app" / "ai" / "sasrec" / "weights" / "sasrec_book5k_e200.pth"
MODEL_VERSION = "sasrec-book5k-e200"
ITEMNUM, MAXLEN, TOP_N = 1000, 35, 5   # 학습 때와 같은 값이어야 한다


def make_engine():
    load_dotenv(BACKEND_DIR / ".env")
    url = os.environ.get("DATABASE_URL")
    if not url:
        url = (
            f"postgresql+psycopg2://{os.environ.get('DB_USER', 'postgres')}:"
            f"{os.environ['DB_PASSWORD']}@{os.environ.get('DB_HOST', 'localhost')}:"
            f"{os.environ.get('DB_PORT', '5432')}/{os.environ.get('DB_NAME', 'book')}"
        )
    return create_engine(url)


def load_model():
    args = SimpleNamespace(device="cpu", hidden_units=50, maxlen=MAXLEN,
                           num_blocks=2, num_heads=1, dropout_rate=0.2, norm_first=False)
    model = SASRec(1, ITEMNUM, args)
    sd = torch.load(CKPT, map_location="cpu")
    sd = {k: v for k, v in sd.items() if not k.startswith("user_emb")}
    model.load_state_dict(sd, strict=False)
    model.eval()
    return model


def main():
    engine = make_engine()
    model = load_model()

    with engine.begin() as con:
        # 회원 목록 (더미 계정 제외), 판매중인 책, 구매 기록(시간순), 인기순위
        members = con.execute(text(
            "SELECT member_id FROM shop.members "
            "WHERE email NOT LIKE '%@bookstore.local' ORDER BY member_id")).scalars().all()
        on_sale = set(con.execute(text(
            "SELECT book_id FROM shop.books WHERE status::text = 'SALE'")).scalars().all())
        rows = con.execute(text("""
            SELECT o.member_id, oi.book_id FROM shop.order_items oi
            JOIN shop.orders o ON o.order_id = oi.order_id
            WHERE o.status::text NOT IN ('CANCELLED', 'PENDING', 'RETURNED')
            ORDER BY o.member_id, o.ordered_at, oi.order_item_id
        """)).all()
        popular = [r[0] for r in con.execute(text("""
            SELECT oi.book_id FROM shop.order_items oi
            JOIN shop.orders o ON o.order_id = oi.order_id
            WHERE o.status::text NOT IN ('CANCELLED', 'PENDING', 'RETURNED')
            GROUP BY 1 ORDER BY count(*) DESC"""))]
    popular = [b for b in popular if b in on_sale]

    hist = {}
    for m, b in rows:
        hist.setdefault(m, []).append(b)

    out = []
    for m in members:
        bought = set(hist.get(m, []))
        if m in hist:                                  # 구매 이력 있음: 모델로 추천
            seq = np.zeros(MAXLEN, dtype=np.int32)
            h = hist[m][-MAXLEN:]
            seq[-len(h):] = h
            cand = np.arange(1, ITEMNUM + 1)
            with torch.no_grad():
                score = model.predict(np.array([m]), np.array([seq]), cand)[0].numpy()
            recs = []
            for idx in np.argsort(-score):             # 점수 높은 순
                b = int(cand[idx])
                if b in bought or b not in on_sale:
                    continue
                recs.append((b, float(score[idx])))
                if len(recs) == TOP_N:
                    break
            algo = "SASREC"
        else:                                          # 구매 이력 없음: 인기순
            recs = [(b, 0.0) for b in popular if b not in bought][:TOP_N]
            algo = "POPULAR"
        for rank, (b, s) in enumerate(recs, 1):
            out.append(dict(member_id=m, book_id=b, score=s, algorithm=algo,
                            rank=rank, model_version=MODEL_VERSION))

    if "--dry" in sys.argv:
        print(len(out), "rows (dry-run, 저장하지 않음)")
        for m in members[:3]:
            print(m, [(r["book_id"], r["algorithm"]) for r in out if r["member_id"] == m])
        return

    # 기존 SASREC/POPULAR 행만 지우고 다시 넣는다 (다른 알고리즘 행은 그대로 둔다)
    with engine.begin() as con:
        con.execute(text("DELETE FROM ai.recommendations WHERE algorithm IN ('SASREC','POPULAR')"))
        con.execute(text("""INSERT INTO ai.recommendations
            (member_id, book_id, score, algorithm, rank, model_version)
            VALUES (:member_id, :book_id, :score, :algorithm, :rank, :model_version)"""), out)
    print(len(out), "rows saved")


if __name__ == "__main__":
    main()
