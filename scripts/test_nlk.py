"""
국립중앙도서관 ISBN 서지정보 API가 책 1권에 대해 무엇을 돌려주는지 그대로 출력해 보는 시험 스크립트.

사용법 (프로젝트 루트에서):
    python scripts/test_nlk.py                  # 기본 ISBN으로 시험
    python scripts/test_nlk.py 9788937460449    # 원하는 ISBN13으로 시험

필요한 .env 값:
    NLK_CERT_KEY=국립중앙도서관에서 받은 인증키
"""
import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

API_URL = "https://www.nl.go.kr/seoji/SearchApi.do"


def main() -> None:
    key = os.getenv("NLK_CERT_KEY")
    if not key:
        raise SystemExit(".env에 NLK_CERT_KEY가 없습니다.")
    isbn = sys.argv[1] if len(sys.argv) > 1 else "9788937460449"

    resp = httpx.get(
        API_URL,
        params={"cert_key": key, "result_style": "json", "page_no": 1, "page_size": 5, "isbn": isbn},
        timeout=15,
    )
    print("HTTP 상태:", resp.status_code)
    try:
        data = resp.json()
    except ValueError:
        print("JSON이 아닌 응답:\n", resp.text[:1000])
        return
    # 키(인증키)는 출력하지 않고 응답 내용만 그대로 보여 줍니다.
    print(json.dumps(data, ensure_ascii=False, indent=2)[:4000])

    # 표지, 책소개 주소가 있으면 한 번 열어 어떤 내용인지 확인합니다.
    docs = data.get("docs") or data.get("DOCS") or []
    if docs:
        doc = docs[0]
        for field in ("TITLE_URL", "BOOK_INTRODUCTION_URL", "BOOK_SUMMARY_URL"):
            url = doc.get(field)
            if url:
                r = httpx.get(url, timeout=15, follow_redirects=True)
                print(f"\n[{field}] {url}\n -> 상태 {r.status_code}, 타입 {r.headers.get('content-type')}")
                if "text" in (r.headers.get("content-type") or ""):
                    print(r.text[:300])


if __name__ == "__main__":
    main()
