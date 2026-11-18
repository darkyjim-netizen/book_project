"""
shop.books 의 비어 있는 책 정보를 외부 API로 채웁니다.

  카카오 책 검색      -> cover_image(표지), description(책 소개 일부)
  국립중앙도서관 ISBN -> page_count(쪽수), 출판일(published_date 가 비어 있을 때만)

이미 값이 있는 칸은 절대 덮어쓰지 않고, 비어 있는 칸만 채웁니다.
중간에 멈춰도 다시 실행하면 남은 책부터 이어서 합니다.

사용법 (backend 폴더에서):
    python scripts/fill_book_info.py --dry --limit 5   # DB는 바꾸지 않고 결과만 출력
    python scripts/fill_book_info.py --limit 5         # 5권만 실제로 채우기
    python scripts/fill_book_info.py                   # 전체 실행

필요한 .env 값:
    KAKAO_REST_API_KEY (또는 KAKAO_REST_API), NLK_CERT_KEY
    DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, (선택) BOOK_DB_NAME=book

못 찾은 책은 scripts/book_info_not_found.csv 에 저장합니다.
"""
import argparse
import csv
import os
import re
import time
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import httpx
import psycopg2
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

KAKAO_URL = "https://dapi.kakao.com/v3/search/book"
NLK_URL = "https://www.nl.go.kr/seoji/SearchApi.do"


class QuotaStop(Exception):
    """호출 한도(429)나 인증 오류가 나서 더 진행할 수 없을 때."""


def kakao_lookup(client: httpx.Client, isbn13: str) -> dict | None:
    resp = client.get(KAKAO_URL, params={"query": isbn13, "target": "isbn", "size": 5})
    if resp.status_code in (401, 403, 429):
        raise QuotaStop(f"카카오 API 응답 {resp.status_code}: {resp.text[:120]}")
    resp.raise_for_status()
    for doc in resp.json().get("documents", []):
        # 응답의 isbn 은 "ISBN10 ISBN13" 형태라 포함 여부로 같은 책을 고릅니다.
        if isbn13 in (doc.get("isbn") or ""):
            return doc
    return None


def original_cover(thumbnail: str) -> str:
    """카카오 썸네일 주소에서 원본 표지 주소를 꺼냅니다(원본이 더 큽니다). 실패하면 썸네일 그대로."""
    if not thumbnail:
        return ""
    fname = parse_qs(urlparse(thumbnail).query).get("fname", [""])[0]
    orig = unquote(fname).replace("http://", "https://", 1)
    return orig if orig.startswith("https://") else thumbnail


def nlk_lookup(client: httpx.Client, key: str, isbn13: str) -> dict | None:
    resp = client.get(NLK_URL, params={
        "cert_key": key, "result_style": "json", "page_no": 1, "page_size": 1, "isbn": isbn13,
    })
    if resp.status_code in (401, 403, 429):
        raise QuotaStop(f"국립중앙도서관 API 응답 {resp.status_code}")
    resp.raise_for_status()
    docs = resp.json().get("docs") or []
    return docs[0] if docs else None


def parse_pages(text: str) -> int | None:
    m = re.search(r"\d+", text or "")
    n = int(m.group()) if m else None
    return n if n and 0 < n < 10000 else None


def parse_date(text: str) -> date | None:
    digits = re.sub(r"\D", "", text or "")[:8]
    try:
        return date(int(digits[:4]), int(digits[4:6]), int(digits[6:8])) if len(digits) == 8 else None
    except ValueError:
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="처리할 최대 권수 (시험용)")
    ap.add_argument("--dry", action="store_true", help="DB를 바꾸지 않고 채울 내용만 출력")
    ap.add_argument("--sleep", type=float, default=0.15, help="호출 사이 대기 시간(초)")
    args = ap.parse_args()

    kakao_key = os.getenv("KAKAO_REST_API_KEY") or os.getenv("KAKAO_REST_API")
    nlk_key = os.getenv("NLK_CERT_KEY")
    if not kakao_key or not nlk_key:
        raise SystemExit(".env에 KAKAO_REST_API_KEY(또는 KAKAO_REST_API)와 NLK_CERT_KEY가 모두 필요합니다.")

    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"), port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("BOOK_DB_NAME", "book"),
        user=os.getenv("DB_USER", "postgres"), password=os.getenv("DB_PASSWORD", ""),
    )
    cur = conn.cursor()
    sql = """
        SELECT book_id, isbn13, title, cover_image, description, page_count, published_date
        FROM shop.books
        WHERE isbn13 IS NOT NULL
          AND (cover_image IS NULL OR description IS NULL OR page_count IS NULL OR published_date IS NULL)
        ORDER BY book_id
    """
    if args.limit:
        sql += f" LIMIT {int(args.limit)}"
    cur.execute(sql)
    targets = cur.fetchall()
    print(f"대상: {len(targets)}권 {'(시험: DB 변경 없음)' if args.dry else ''}")

    stats = {"cover": 0, "description": 0, "page_count": 0, "published_date": 0}
    not_found, errors = [], 0
    try:
        with httpx.Client(headers={"Authorization": f"KakaoAK {kakao_key}"}, timeout=15) as kakao, \
                httpx.Client(timeout=15) as nlk:
            for idx, (bid, isbn, title, cover, desc, pages, pub) in enumerate(targets, 1):
                new = {}
                try:
                    kdoc = kakao_lookup(kakao, isbn) if (cover is None or desc is None or pub is None) else None
                    ndoc = nlk_lookup(nlk, nlk_key, isbn) if (pages is None or pub is None) else None
                except httpx.HTTPError as exc:
                    errors += 1
                    print(f"  [{bid}] 네트워크 오류: {type(exc).__name__}")
                    continue

                if kdoc:
                    if cover is None and kdoc.get("thumbnail"):
                        new["cover_image"] = original_cover(kdoc["thumbnail"])
                    if desc is None and (kdoc.get("contents") or "").strip():
                        new["description"] = kdoc["contents"].strip()
                    if pub is None and parse_date(kdoc.get("datetime", "")):
                        new["published_date"] = parse_date(kdoc["datetime"])
                if ndoc:
                    if pages is None and parse_pages(ndoc.get("PAGE")):
                        new["page_count"] = parse_pages(ndoc["PAGE"])
                    if pub is None and "published_date" not in new:
                        d = parse_date(ndoc.get("REAL_PUBLISH_DATE") or ndoc.get("PUBLISH_PREDATE"))
                        if d:
                            new["published_date"] = d

                if not kdoc and not ndoc:
                    not_found.append((bid, isbn, title))
                if new:
                    for k in new:
                        stats["cover" if k == "cover_image" else k] += 1
                    if args.dry:
                        shown = {k: (str(v)[:50] + "…" if len(str(v)) > 50 else v) for k, v in new.items()}
                        print(f"  [{bid}] {title[:20]}: {shown}")
                    else:
                        sets = ", ".join(f"{k} = %s" for k in new)
                        cur.execute(f"UPDATE shop.books SET {sets}, updated_at = now() WHERE book_id = %s",
                                    [*new.values(), bid])
                if not args.dry and idx % 50 == 0:
                    conn.commit()
                    print(f"  ... {idx}/{len(targets)}권 처리, 저장됨")
                time.sleep(args.sleep)
    except QuotaStop as exc:
        print(f"\n중단: {exc}\n여기까지의 결과는 저장하고 끝냅니다. 나중에 다시 실행하면 이어서 합니다.")
    finally:
        if not args.dry:
            conn.commit()
        conn.close()

    print(f"\n채운 칸: 표지 {stats['cover']}, 소개 {stats['description']}, 쪽수 {stats['page_count']}, 출판일 {stats['published_date']}")
    print(f"두 곳 모두에서 못 찾은 책: {len(not_found)}권, 네트워크 오류: {errors}권")
    if not_found:
        out = ROOT / "scripts" / "book_info_not_found.csv"
        with open(out, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f); w.writerow(["book_id", "isbn13", "title"]); w.writerows(not_found)
        print(f"목록 저장: {out}")


if __name__ == "__main__":
    main()