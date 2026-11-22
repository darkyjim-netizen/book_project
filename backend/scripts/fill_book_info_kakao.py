"""
카카오(다음) 책 검색 API로 products의 표지(cover_image_url)와 소개(description)를 채웁니다.

사용법 (프로젝트 루트에서):
    python scripts/fill_book_info_kakao.py --limit 5     # 먼저 5권만 시험
    python scripts/fill_book_info_kakao.py               # 전체 실행 (이미 채운 책은 건너뜀)

필요한 .env 값:
    KAKAO_REST_API_KEY=카카오 개발자 사이트에서 받은 REST API 키
    DB_HOST, DB_PORT, DB_USER, DB_PASSWORD  (이미 있음)
    BOOK_DB_NAME=book   (없으면 기본값 book 사용. .env의 DB_NAME은 쓰지 않습니다)

결과:
    못 찾은 책은 scripts/kakao_not_found.csv 에 저장됩니다.
"""
import argparse
import csv
import os
import time
from pathlib import Path

import httpx
import psycopg2
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

API_URL = "https://dapi.kakao.com/v3/search/book"


def fetch_book(client: httpx.Client, isbn13: str) -> dict | None:
    """ISBN13으로 책 한 권을 조회합니다. 못 찾으면 None."""
    resp = client.get(API_URL, params={"query": isbn13, "target": "isbn", "size": 5})
    resp.raise_for_status()
    for doc in resp.json().get("documents", []):
        # 응답의 isbn은 "ISBN10 ISBN13" 형태라 포함 여부로 맞는 책을 고릅니다.
        if isbn13 in (doc.get("isbn") or ""):
            return doc
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="처리할 최대 권수 (시험용)")
    args = parser.parse_args()

    key = os.getenv("KAKAO_REST_API_KEY")
    if not key:
        raise SystemExit(".env에 KAKAO_REST_API_KEY가 없습니다.")

    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"), port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("BOOK_DB_NAME", "book"),
        user=os.getenv("DB_USER", "postgres"), password=os.getenv("DB_PASSWORD", ""),
    )
    cur = conn.cursor()
    # 표지가 아직 없는 책만 대상으로 하므로 중간에 멈춰도 다시 실행하면 이어서 합니다.
    sql = "SELECT id, isbn, title FROM products WHERE cover_image_url IS NULL ORDER BY id"
    if args.limit:
        sql += f" LIMIT {int(args.limit)}"
    cur.execute(sql)
    targets = cur.fetchall()
    print(f"조회 대상: {len(targets)}권")

    not_found, ok = [], 0
    headers = {"Authorization": f"KakaoAK {key}"}
    with httpx.Client(headers=headers, timeout=10) as client:
        for idx, (pid, isbn, title) in enumerate(targets, 1):
            try:
                doc = fetch_book(client, isbn.strip())
            except httpx.HTTPError as exc:
                print(f"[{idx}] 오류 id={pid} {exc}")
                not_found.append((pid, isbn, title, f"오류: {exc}"))
                continue

            thumb = (doc or {}).get("thumbnail") or ""
            if not thumb:
                not_found.append((pid, isbn, title, "결과 없음 또는 표지 없음"))
                continue

            cur.execute(
                "UPDATE products SET cover_image_url = %s, "
                "description = COALESCE(description, NULLIF(%s, '')), updated_at = now() "
                "WHERE id = %s",
                (thumb, doc.get("contents"), pid),
            )
            conn.commit()
            ok += 1
            if idx % 50 == 0:
                print(f"진행 {idx}/{len(targets)} (성공 {ok})")
            time.sleep(0.1)  # 호출 간격

    cur.close()
    conn.close()

    out = ROOT / "scripts" / "kakao_not_found.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["id", "isbn", "title", "reason"])
        w.writerows(not_found)
    print(f"완료: 성공 {ok}권, 못 찾음 {len(not_found)}권 -> {out}")


if __name__ == "__main__":
    main()
