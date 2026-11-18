"""현재 DB 도서를 보존한 채 판매 도서를 최소 1,000권까지 채운다.

실행: python -m team_backend.scripts.seed_books_to_1000
"""

from datetime import date, timedelta

from sqlalchemy import text

from team_backend.app.core.database import SessionLocal


TARGET_COUNT = 1000
ADJECTIVES = ["고요한", "빛나는", "다정한", "새로운", "깊은", "작은", "오늘의", "느린", "단단한", "푸른"]
TOPICS = ["문장", "세계", "마음", "기록", "시간", "생각", "여행", "발견", "질문", "이야기"]


def main() -> None:
    """필요한 수만큼만 추가하므로 여러 번 실행해도 1,000권을 넘기지 않는다."""
    db = SessionLocal()
    try:
        current = db.scalar(text("SELECT count(*) FROM shop.books")) or 0
        missing = max(0, TARGET_COUNT - current)
        if not missing:
            print(f"이미 {current}권이 있어 추가하지 않았습니다.")
            return

        categories = [row[0] for row in db.execute(text("""
            SELECT category_id FROM shop.categories
            WHERE depth >= 2 ORDER BY category_id
        """))]
        publishers = [row[0] for row in db.execute(text("""
            SELECT publisher_id FROM shop.publishers ORDER BY publisher_id
        """))]
        authors = [row[0] for row in db.execute(text("""
            SELECT author_id FROM shop.authors ORDER BY author_id
        """))]
        if not categories or not publishers or not authors:
            raise RuntimeError("카테고리·출판사·저자 기준 데이터를 먼저 입력해 주세요.")

        # 기존 ISBN 뒤에서 시작해 충돌 없이 13자리 ISBN을 만든다.
        last_no = db.scalar(text("""
            SELECT COALESCE(MAX(CAST(isbn13 AS numeric)), 9799000000000)
            FROM shop.books WHERE isbn13 ~ '^[0-9]{13}$'
        """))
        start_no = max(int(last_no) + 1, 9799000000001)
        books = []
        for index in range(missing):
            serial = current + index + 1
            books.append({
                "isbn13": str(start_no + index)[-13:],
                "title": f"{ADJECTIVES[index % len(ADJECTIVES)]} {TOPICS[index % len(TOPICS)]} {serial}",
                "category_id": categories[index % len(categories)],
                "publisher_id": publishers[index % len(publishers)],
                "list_price": 12000 + (index % 12) * 1000,
                "sale_price": int((12000 + (index % 12) * 1000) * 0.9),
                "stock_qty": 20 + (index % 80),
                "published_date": date.today() - timedelta(days=index % 730),
            })

        rows = db.execute(text("""
            INSERT INTO shop.books (
                isbn13, title, category_id, publisher_id, list_price, sale_price,
                discount_rate, stock_qty, status, is_domestic, language_code,
                published_date, summary, description
            ) VALUES (
                :isbn13, :title, :category_id, :publisher_id, :list_price, :sale_price,
                10, :stock_qty, 'SALE', true, 'ko', :published_date,
                '메인 페이지 표시를 위한 테스트 도서입니다.',
                '개발 환경에서 목록, 슬라이더, 검색 및 페이징을 확인하기 위해 생성한 테스트 도서입니다.'
            ) RETURNING book_id
        """), books).scalars().all()
        db.execute(text("""
            INSERT INTO shop.book_authors (book_id, author_id, role, sort_order)
            VALUES (:book_id, :author_id, 'AUTHOR', 0)
        """), [
            {"book_id": book_id, "author_id": authors[index % len(authors)]}
            for index, book_id in enumerate(rows)
        ])
        db.commit()
        print(f"{len(rows)}권 추가 완료: 총 {current + len(rows)}권")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
