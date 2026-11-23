"""개발용 서점 API의 주요 기능을 빠르게 점검하고, 테스트 중 변경한 DB 데이터는 롤백한다."""
import os
import logging
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

# 앱 설정을 불러오기 전에 모의 결제를 켜고, 로그를 임시 폴더에 저장한다.
os.environ["PG_MOCK_MODE"] = "true"
test_logs = TemporaryDirectory(prefix="bookstore-smoke-")
os.environ["LOG_DIR"] = test_logs.name
# 어디서 실행하든 backend를 작업 폴더로 삼아 app 패키지를 불러온다.
os.chdir(Path(__file__).resolve().parents[1])
sys.path.insert(0, str(Path.cwd()))

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import engine, get_db
from backend.main import app
from app.models.book import Book
from app.models.enums import BookStatus, MemberRole
from app.models.member import Member


def main():
    # 운영 환경이거나 모의 결제가 꺼져 있으면 실행을 중단한다.
    if settings.is_production or not settings.PG_MOCK_MODE:
        raise SystemExit("개발용 데이터베이스와 모의 결제 환경에서만 실행하세요.")

    with engine.connect() as connection:
        transaction = connection.begin()

        # API 요청도 같은 DB 연결을 사용한다. 요청에서 커밋해도 바깥 트랜잭션은 유지된다.
        def test_db():
            with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
                yield session

        app.dependency_overrides[get_db] = test_db
        try:
            smoke(connection)
        finally:
            # 점검이 실패해도 원래 DB 설정을 복구하고 이번 실행의 DB 변경을 되돌린다.
            app.dependency_overrides.pop(get_db, None)
            transaction.rollback()


def smoke(connection):
    async def local_client(scope, receive, send):
        # 로그인 감사 로그의 PostgreSQL inet 컬럼에 저장할 수 있도록 요청 IP를 지정한다.
        await app({**scope, "client": ("127.0.0.1", 50000)}, receive, send)

    # 공통 API 경로로 요청을 보내고, 예상 상태 코드를 확인한 뒤 JSON 응답을 반환한다.
    def check(client, method, path, status=200, **kwargs):
        response = client.request(method, "/api/v1" + path, **kwargs)
        assert response.status_code == status, (path, status, response.status_code, response.text[:300])
        print(f"{response.status_code} {method} {path}", flush=True)
        return response.json() if response.content and response.headers.get("content-type", "").startswith("application/json") else None

    def register(client, email):
        check(client, "POST", "/auth/signup", 201, json={
            "email": email, "name": "Smoke Test", "password": "SmokeTest42!", "password_confirm": "SmokeTest42!"
        })

    # 실행마다 다른 이메일을 쓰고, 비회원·일반 회원·관리자의 쿠키를 따로 유지한다.
    run_id = uuid4().hex[:12]
    guest = TestClient(local_client)
    member = TestClient(local_client)
    admin = TestClient(local_client)
    # 수량을 2권까지 늘릴 수 있는 판매 중인 도서를 기존 데이터에서 고른다.
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        book = session.execute(select(Book.book_id, Book.title).where(
            Book.stock_qty >= 2, Book.status == BookStatus.SALE, Book.sale_price > 0
        ).limit(1)).one_or_none()
    assert book, "테스트를 실행하려면 재고가 2권 이상이고 판매가가 0원보다 큰 판매 중 도서가 필요합니다."
    book_id, title = book

    # 비회원이 공개 정보를 조회할 수 있고 관리자 화면에는 접근할 수 없는지 확인한다.
    check(guest, "GET", "/books", params={"keyword": title, "size": 1})
    check(guest, "GET", "/books/bestsellers", params={"days": 7, "limit": 2})
    check(guest, "GET", f"/books/{book_id}")
    check(guest, "GET", f"/books/{book_id}/review-stats")
    check(guest, "GET", "/notices")
    check(guest, "GET", "/faqs")
    check(guest, "GET", "/admin/dashboard", 401)

    # 비회원이 장바구니 수량을 바꿔 주문하고, 주문 후 장바구니가 비워지는지 확인한다.
    guest_email = f"smoke-{run_id}@example.com"
    cart = check(guest, "POST", "/cart/items", json={"book_id": book_id, "quantity": 1})
    item_id = cart["items"][0]["cart_item_id"]
    check(guest, "PUT", f"/cart/items/{item_id}", json={"quantity": 2})
    order = check(guest, "POST", "/orders", json={
        "orderer_name": "Smoke Test", "orderer_email": guest_email, "orderer_phone": "01012345678",
        "receiver": "Smoke Test", "receiver_phone": "01012345678", "zipcode": "06236",
        "address1": "서울특별시 테스트 주소", "payment_method": "CARD",
    })
    assert order["items"][0]["quantity"] == 2
    assert not check(guest, "GET", "/cart")["items"]
    # 비회원 주문 토큰 없이 결제가 거절되고, 토큰을 주면 모의 결제와 주문 조회가 되는지 확인한다.
    pay_path = f"/orders/{order['order_id']}/pay"
    check(guest, "POST", pay_path, 401, json={})
    payment = check(guest, "POST", pay_path, json={}, headers={"X-Guest-Order-Token": order["guest_order_token"]})
    assert payment["status"] == "PAID"
    looked_up = check(guest, "GET", "/orders/lookup", params={"order_no": order["order_no"], "email": guest_email})
    assert looked_up["payment"]["status"] == "PAID"

    # 테스트 계정 두 개를 가입시키고, 한 계정에 관리자 권한을 부여한 뒤 각각 로그인한다.
    member_email, admin_email = f"smoke-member-{run_id}@example.com", f"smoke-admin-{run_id}@example.com"
    register(member, member_email)
    register(admin, admin_email)
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        session.scalar(select(Member).where(Member.email == admin_email)).role = MemberRole.ADMIN
        session.commit()
    for client, email in [(member, member_email), (admin, admin_email)]:
        check(client, "POST", "/auth/login", json={"email": email, "password": "SmokeTest42!"})

    # 일반 회원의 관리자 API 접근을 막고, 주소 조회와 찜 기능은 허용하는지 확인한다.
    check(member, "GET", "/admin/purchase-demographics", 403)
    check(member, "GET", "/members/me/addresses")
    check(member, "POST", "/wishlist/" + str(book_id))
    assert check(member, "GET", "/wishlist")["items"][0]["book_id"] == book_id
    # 일반 회원이 등록한 비밀 문의에 관리자가 답변하고, 작성자가 답변을 조회한다.
    question = check(member, "POST", "/qna", 201, json={"title": "Smoke test", "content": "Test question", "is_secret": True})
    qid = question["question_id"]
    check(admin, "POST", f"/admin/qna/{qid}/answer", json={"content": "Test answer"})
    assert check(member, "GET", f"/qna/{qid}")["answers"][0]["content"] == "Test answer"
    # 관리자 구매 통계에 테스트 주문의 배송 지역인 서울특별시가 표시되는지 확인한다.
    stats = check(admin, "GET", "/admin/purchase-demographics")
    assert any(item["label"] == "서울특별시" for item in stats["regions"])
    print("Smoke checks passed; transaction will be rolled back.", flush=True)


if __name__ == "__main__":
    try:
        main()
    finally:
        # 로그 파일을 닫은 뒤 임시 로그 폴더를 삭제한다.
        logging.shutdown()
        test_logs.cleanup()

