# ========================= 초보자용 안내 =========================
# 이 파일은 AI 기능을 시험하기 위한 가상 쇼핑 데이터를 DB에 추가한다.
# self는 지금 작업 중인 생성기 객체를 가리킨다.
# db.execute(...)는 SQL 실행, db.commit()은 변경 내용을 DB에 확정하는 뜻이다.
# SQL 안의 :name은 파이썬 딕셔너리의 같은 이름 값이 들어갈 자리다.
# -> int, -> str 같은 표시는 함수가 돌려주는 값의 자료형을 설명한다.
# 실행 예: python -m scripts.generate_demo_data --members 300 --days 365
# 실행하면 DB 내용이 바뀌므로 개발/테스트용 데이터베이스에서 실행한다.
# ===================================================================


"""데모/학습용 데이터 생성 스크립트.

AI 모델(협업 필터링, 감성 분석, 판매 예측, 이탈 예측)이 의미 있는 결과를
내려면 충분한 양의 회원·주문·리뷰 데이터가 필요하다.
이 스크립트는 통계적으로 그럴듯한 합성 데이터를 생성한다.

실행
----
    cd backend
    python -m scripts.generate_demo_data --members 300 --days 365

생성 내용
---------
* 관리자 1명 + 일반 회원 N명 (가입일을 과거로 분산)
* 회원별 선호 카테고리에 편중된 주문 이력 (요일/월별 계절성 반영)
* 주문 상태 분포(결제완료 ~ 구매확정 ~ 취소)
* 평점과 어조가 일치하는 한국어 리뷰
* 조회 이력, 위시리스트, 1:1 상담, Q&A
"""

# 함수의 타입 표시에서 아직 정의 중인 이름을 사용할 수 있게 한다.
from __future__ import annotations

# 명령 프롬프트에서 --members 같은 실행 옵션을 읽는다.
import argparse

# 월별 주문 비중을 계산하는 삼각함수에 사용한다.
import math

# 가상 이름, 도서, 주문 상태 등을 무작위로 고른다.
import random

# 파이썬 모듈 검색 경로를 관리한다.
import sys

# 날짜와 시간을 만들고 계산한다.
from datetime import datetime, timedelta, timezone

# 현재 파일의 위치를 운영체제에 맞게 다룬다.
from pathlib import Path

# backend 폴더를 파이썬 모듈 검색 경로에 추가한다.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# SQL 문장을 SQLAlchemy에 전달한다. SQL의 :이름은 값이 들어갈 자리다.
from sqlalchemy import text  # noqa: E402

# 프로젝트에서 DB 연결 세션을 만드는 함수다.
from team_backend.app.core.database import SessionLocal  # noqa: E402

# 비밀번호를 원문 대신 해시로 바꾸는 함수다.
from team_backend.app.core.security import hash_password  # noqa: E402



# 한국 시간대(UTC보다 9시간 빠름)를 저장한다.
KST = timezone(timedelta(hours=9))

# 가상 회원 이름에 사용할 성 목록이다.
LAST_NAMES = ["김", "이", "박", "최", "정", "강", "조", "윤", "장", "임", "한", "오", "서", "신", "권"]

# 가상 회원 이름에 사용할 이름 목록이다.
FIRST_NAMES = [
    "민준", "서윤", "도윤", "지우", "예준", "하윤", "주원", "지민", "지호", "수아",
    "건우", "다은", "우진", "서연", "연우", "유진", "현우", "소율", "시우", "채원",
]

# 가상 이메일 주소 끝부분으로 쓸 도메인 목록이다.
DOMAINS = ["example.com", "test.co.kr", "mail.net", "bookmail.kr"]

# 높은 평점에 사용할 긍정 리뷰 예문이다.
POSITIVE_TEMPLATES = [
    "기대 이상으로 좋았습니다. 문장이 깔끔하고 몰입도가 높아서 하루 만에 다 읽었어요.",
    "내용이 알차고 설명이 친절해서 입문자에게도 추천합니다. 배송도 빠르고 포장이 깔끔했어요.",
    "구성이 체계적이고 예시가 풍부합니다. 실무에 바로 적용할 수 있어서 아주 만족합니다.",
    "오랜만에 여운이 남는 책이었습니다. 문장이 아름답고 감동적이라 선물용으로도 좋네요.",
    "정말 유익한 책입니다. 핵심을 명확하게 짚어 주고 흐름이 자연스러워 술술 읽혔습니다.",
    "완벽한 입문서입니다. 어려운 개념도 쉽게 풀어 주어서 이해가 잘 되었어요. 강추합니다.",
    "믿음이 가는 저자의 통찰이 담겨 있습니다. 다시 읽고 싶은 책이라 소장하기로 했어요.",
]
# 보통 평점에 사용할 중립 리뷰 예문이다.
NEUTRAL_TEMPLATES = [
    "무난한 책입니다. 기대만큼 특별하진 않았지만 참고 자료로는 쓸 만합니다.",
    "내용은 평범하지만 정리가 되어 있어 가볍게 읽기 좋습니다. 가격은 조금 있는 편입니다.",
    "전반적으로 괜찮았고 일부 장은 도움이 되었습니다. 다만 중반부가 다소 반복적이었어요.",
    "주제 자체는 흥미로운데 깊이는 아쉽습니다. 입문용으로는 충분해 보입니다.",
]
# 낮은 평점에 사용할 부정 리뷰 예문이다.
NEGATIVE_TEMPLATES = [
    "기대에 비해 실망스러웠습니다. 내용이 부실하고 설명이 산만해서 집중이 잘 안 됐어요.",
    "번역이 어색하고 오타가 많아 읽기 불편했습니다. 가격 대비 아쉬운 구성입니다.",
    "지루하고 반복적인 서술이 많았습니다. 후회가 남는 선택이었어요.",
    "배송 중에 표지가 구겨져 왔고, 내용도 뻔한 이야기의 반복이라 별로였습니다.",
    "어렵게만 쓰여 있고 정작 핵심 설명이 부족합니다. 초보자에게는 추천하지 않습니다.",
]

# 문의 게시판에 넣을 분류·제목·본문 예시다.
QNA_SAMPLES = [
    ("ORDER", "주문한 도서의 배송 예정일을 알고 싶습니다", "어제 결제한 주문의 도착 예정일을 알고 싶습니다."),
    ("PRODUCT", "이 책의 개정판 출간 예정이 있나요?", "구매 전에 개정판 일정이 있는지 확인하고 싶습니다."),
    ("SHIPPING", "배송지를 변경할 수 있을까요?", "아직 상품 준비 중인데 주소를 변경하고 싶습니다."),
    ("PAYMENT", "현금영수증 재발급 요청", "결제 시 신청을 못 했습니다. 재발급 가능한가요?"),
    ("ETC", "품절 도서 재입고 문의", "관심 도서가 품절인데 재입고 일정이 있는지 알고 싶습니다."),
]

# 1:1 상담에 넣을 가상 문의 문장이다.
CHAT_SAMPLES = [
    "안녕하세요, 주문한 책이 아직 배송 출발하지 않았습니다. 확인 부탁드립니다.",
    "배송비 정책이 어떻게 되는지 알려주세요.",
    "포인트 사용 가능한 최소 금액이 있나요?",
    "교환 접수는 어디서 하면 되나요?",
]


# 성 목록과 이름 목록에서 하나씩 뽑아 이름을 만든다.
def random_name() -> str:
    return random.choice(LAST_NAMES) + random.choice(FIRST_NAMES)


# 요일, 월, 급여일에 따라 주문이 달라지도록 확률 가중치를 계산한다.
def seasonal_factor(day: datetime) -> float:
    """요일/월 계절성 가중치를 반환한다."""
    weekday_weight = [1.05, 1.0, 1.0, 1.02, 1.12, 0.92, 0.85][day.weekday()]            # weekday()는 월요일 0부터 일요일 6까지를 반환한다. 요일마다 주문 비중을 다르게 둔다.
    month_weight = 1.0 + 0.18 * math.sin((day.month - 2) / 12 * 2 * math.pi)            # sin 함수로 월별 주문 비중을 조금씩 다르게 만든다.
    payday_weight = 1.15 if day.day in (10, 11, 25, 26) else 1.0                        # 급여일로 정한 날에는 주문 확률을 15% 높인다.
    return weekday_weight * month_weight * payday_weight                                # 요일·월·급여일 가중치를 곱한 값을 반환한다.


# DB에 테스트용 회원과 주문 데이터를 넣는 작업을 모은 클래스다.
class DemoDataGenerator:
    def __init__(self, db, members: int, days: int, seed: int = 42):        # 객체를 처음 만들 때 실행되는 초기화 함수다.
        self.db = db                                                        # DB 질의에 쓸 연결 세션을 객체에 저장한다.
        self.member_count = members                                         # 생성할 일반 회원 수를 저장한다.
        self.days = days                                                    # 데이터를 과거 며칠까지 만들지 저장한다.
        self.books: list[dict] = []                                         # DB에서 가져온 도서 정보를 담을 빈 목록이다.
        self.member_ids: list[int] = []                                     # 생성한 일반 회원의 DB 번호를 담을 목록이다.
        self.member_prefs: dict[int, list[int]] = {}                        # 회원 번호마다 선호 카테고리 번호를 저장한다.
        random.seed(seed)                                                   # 같은 seed를 쓰면 무작위 결과를 다시 만들기 쉽다.

# ------------------------------------------------------------------ 준비
# 판매 중이거나 품절된 도서를 DB에서 읽어온다.
    def load_books(self) -> None:
        
# DB에서 회원 번호를 다시 조회한다.
        rows = self.db.execute(
            text(
                """
                SELECT book_id, category_id, sale_price::float, point_rate::float
                  FROM shop.books WHERE status IN ('SALE','SOLDOUT') ORDER BY book_id
                """
            )
        ).all()
        
# DB 결과를 사용하기 편한 딕셔너리 목록으로 변환한다.
        self.books = [
            {"book_id": r[0], "category_id": r[1], "sale_price": r[2], "point_rate": r[3]}
            for r in rows
        ]
        
# 도서가 없으면 주문을 만들 수 없으므로 프로그램을 멈춘다.
        if not self.books:
            raise SystemExit("도서 데이터가 없습니다. 02_seed_master.sql 을 먼저 실행하세요.")
        print(f"  도서 {len(self.books)}종 로드")


# ------------------------------------------------------------------ 회원
# 테스트 관리자·상담원·일반 회원을 DB에 추가한다.
    def create_members(self) -> None:
# 관리자 비밀번호를 해시한 문자열로 바꾼다.
        admin_hash = hash_password("admin1234")
        self.db.execute(
            text(
                """
                INSERT INTO shop.members (email, password_hash, name, nickname, phone, gender,
                                          role, status, grade_id, point_balance, created_at)
                VALUES ('admin@bookstore.local', :pw, '관리자', '관리자', '010-0000-0000', 'N',
                        'ADMIN', 'ACTIVE', 5, 100000, now() - interval '400 days')
                ON CONFLICT (email) DO NOTHING
                """
            ),
            {"pw": admin_hash},
        )
        
        self.db.execute(
            text(
                """
                INSERT INTO shop.members (email, password_hash, name, nickname, phone, gender,
                                          role, status, grade_id, created_at)
                VALUES ('staff@bookstore.local', :pw, '상담원', '상담원', '010-0000-0001', 'N',
                        'STAFF', 'ACTIVE', 1, now() - interval '300 days')
                ON CONFLICT (email) DO NOTHING
                """
            ),
            {"pw": hash_password("staff1234")},
        )

# 일반 테스트 회원이 함께 쓸 비밀번호를 해시한다.
        user_hash = hash_password("user1234")
        
# 도서들에 있는 중복 없는 카테고리 번호를 모아 정렬한다.
        categories = sorted({b["category_id"] for b in self.books})

# DB에 한꺼번에 넣을 회원 정보를 모을 목록이다.
        payload = []
        
# 1부터 설정한 회원 수만큼 반복한다. range의 마지막 숫자는 포함되지 않는다.
        for i in range(1, self.member_count + 1):
            
# 현재 한국 시각에서 무작위 일수를 빼 가상의 가입 시각을 만든다.
            created = datetime.now(KST) - timedelta(days=random.randint(5, self.days))
            payload.append(
                {
# 이름, 이메일, 연락처, 가입일 등 회원 한 명의 정보를 딕셔너리에 담는다.
                    "email": f"user{i}@{random.choice(DOMAINS)}" if i > 5 else f"user{i}@example.com",
                    "pw": user_hash,
                    "name": random_name(),
                    "phone": f"010-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}",
                    "gender": random.choice(["M", "F", "N"]),
                    "created": created,
                    "last_login": created + timedelta(days=random.randint(0, 60)),
                    "marketing": random.random() < 0.6,
                }
            )

        self.db.execute(
            text(
                """
                INSERT INTO shop.members (email, password_hash, name, nickname, phone, gender,
                                          role, status, grade_id, created_at, last_login_at,
                                          marketing_agree, email_agree, sms_agree)
                VALUES (:email, :pw, :name, :name, :phone, CAST(:gender AS shop.gender_type),
                        'USER', 'ACTIVE', 1, :created, :last_login, :marketing, :marketing, :marketing)
                ON CONFLICT (email) DO NOTHING
                """
            ),
            payload,
        )
        
# 앞에서 실행한 DB 변경을 확정한다. 확정 전 변경은 롤백될 수 있다.
        self.db.commit()
        rows = self.db.execute(
            text("SELECT member_id FROM shop.members WHERE role = 'USER' ORDER BY member_id")
        ).all()
# 조회 결과에서 회원 번호만 꺼내 목록에 저장한다.
        self.member_ids = [r[0] for r in rows]
        for member_id in self.member_ids:
            
# 회원마다 선호 카테고리를 최대 3개 무작위로 정한다.
            self.member_prefs[member_id] = random.sample(categories, k=min(3, len(categories)))
        print(f"  회원 {len(self.member_ids)}명 생성 (+ 관리자/상담원)")


# ------------------------------------------------------------------ 주문
# 회원이 좋아하는 카테고리의 책이 더 잘 뽑히게 도서를 선택한다.
    def pick_books(self, member_id: int, count: int) -> list[dict]:
        """회원 선호 카테고리에 가중치를 둔 도서 선택."""
        
# 해당 회원의 선호 카테고리를 가져온다.
        prefs = self.member_prefs.get(member_id, [])
        
# 선호 책의 선택 가중치는 3, 나머지는 1로 높낮이를 준다.
        weights = [3.0 if b["category_id"] in prefs else 1.0 for b in self.books]
        picked: list[dict] = []
        attempts = 0
        
# 필요한 수만큼 골랐거나 반복 제한에 닿을 때까지 계속 뽑는다.
        while len(picked) < count and attempts < count * 10:
            
# 가중치에 따라 책 하나를 무작위로 고른다.
            book = random.choices(self.books, weights=weights, k=1)[0]
            if book not in picked:
                picked.append(book)
            attempts += 1
        return picked

# 주문과 주문상품, 결제, 배송 정보를 DB에 만든다.
    def create_orders(self) -> None:
        
# 상태별 목록의 반복 횟수로 주문 상태가 선택될 비율을 정한다.
        status_pool = (
            ["CONFIRMED"] * 46 + ["DELIVERED"] * 20 + ["SHIPPING"] * 10
            + ["PREPARING"] * 8 + ["PAID"] * 8 + ["CANCELLED"] * 6 + ["PENDING"] * 2
        )
        
# 카드나 간편결제 등 결제 수단별 선택 비율을 정한다.
        methods = (
            ["CARD"] * 55 + ["KAKAOPAY"] * 15 + ["NAVERPAY"] * 10
            + ["TOSSPAY"] * 8 + ["VBANK"] * 7 + ["TRANSFER"] * 5
        )
        order_count = 0
        item_count = 0
        
# 구매 확정 주문 가운데 리뷰 후보를 모아둘 목록이다.
        review_rows: list[dict] = []
        now = datetime.now(KST)
        for member_id in self.member_ids:
            
# 회원별 주문 횟수: 멱법칙 분포 (소수의 헤비 유저)  
# 대부분은 적게, 일부 회원은 많이 주문하도록 횟수를 뽑는다.
            orders_for_member = max(0, int(random.paretovariate(1.4)) - 1)
            
# 한 회원의 주문 수가 최대 18건을 넘지 않도록 제한한다.
            orders_for_member = min(orders_for_member, 18)
            for _ in range(orders_for_member):
                
# 최근 날짜가 더 자주 선택되도록 과거 날짜를 뽑는다.
                days_ago = int(random.triangular(0, self.days, self.days * 0.35))
                
# 선택한 날짜에 무작위 시각을 더해 주문 시각을 만든다.
                ordered_at = now - timedelta(
                    days=days_ago, hours=random.randint(0, 23), minutes=random.randint(0, 59)
                )
                
# 계절별 가중치에 따라 이 주문 생성을 건너뛸 수도 있다.
                if random.random() > min(seasonal_factor(ordered_at) / 1.3, 1.0):
                    continue

# 정해둔 비율에 따라 주문 상태를 하나 고른다.
                status = random.choice(status_pool)
                
# 주문에 넣을 책을 1~3권 선택한다.
                items = self.pick_books(member_id, random.randint(1, 3))
                if not items:
                    continue
                item_amount = 0.0
                
# 선택한 책마다 주문상품 정보를 별도로 저장한다.
                for book in items:
                    
# 대부분 한 권, 일부는 두 권 주문하게 한다.
                    quantity = 1 if random.random() < 0.85 else 2
                    book["_qty"] = quantity
                    
# 책 가격과 수량을 곱한 금액을 상품 합계에 더한다.
                    item_amount += book["sale_price"] * quantity

# 일부 주문에 상품 합계의 10% 쿠폰을 적용한다.
                coupon_amount = round(item_amount * 0.1) if random.random() < 0.18 else 0
                
# 일부 주문에서 사용할 포인트를 무작위로 정한다.
                point_used = random.choice([0, 0, 0, 500, 1000, 2000]) if item_amount > 20000 else 0
                
# 상품 합계가 2만 원 이상이면 무료, 그보다 적으면 배송비 3천 원을 붙인다.
                ship_fee = 0 if item_amount >= 20000 else 3000
                
# 상품합계 - 쿠폰 - 포인트 + 배송비를 계산하고, 최저 금액은 0원으로 둔다.
                total = max(item_amount - coupon_amount - point_used + ship_fee, 0)
                
# 쿠폰을 뺀 상품 금액의 1.5%를 적립 포인트로 계산한다.
                point_saved = int((item_amount - coupon_amount) * 0.015)

# 주문을 저장한 뒤 RETURNING으로 방금 생성된 주문 번호를 받는다.
                order_id = self.db.execute(
                    text(
                        """
                        INSERT INTO shop.orders
                            (order_no, member_id, orderer_name, orderer_phone, orderer_email,
                             status, item_amount, discount_amount, coupon_amount, point_used,
                             ship_fee, total_amount, point_saved, receiver, receiver_phone,
                             zipcode, address1, address2, ordered_at, paid_at, delivered_at,
                             confirmed_at, cancelled_at)
                        SELECT :order_no, m.member_id, m.name, m.phone, m.email,
                               CAST(:status AS shop.order_status), :item_amount, 0, :coupon, :point_used,
                               :ship_fee, :total, :point_saved, m.name, m.phone,
                               '06236', '서울특별시 강남구 테헤란로 123', '4층',
                               :ordered_at,

                               CASE WHEN :status <> 'PENDING' THEN :ordered_at END,
                               CASE WHEN :status IN ('DELIVERED','CONFIRMED')
                                    THEN :ordered_at + interval '2 days' END,
                               CASE WHEN :status = 'CONFIRMED'
                                    THEN :ordered_at + interval '9 days' END,
                               CASE WHEN :status = 'CANCELLED'
                                    THEN :ordered_at + interval '1 day' END
                          FROM shop.members m WHERE m.member_id = :member_id
                        RETURNING order_id
                        """
                    ),
                    {
# 주문 날짜와 무작위 숫자를 붙여 테스트 주문 번호를 만든다.
                        "order_no": f"{ordered_at.strftime('%Y%m%d')}{random.randint(10000000, 99999999)}",
                        "member_id": member_id,
                        "status": status,
                        "item_amount": item_amount,
                        "coupon": coupon_amount,
                        "point_used": point_used,
                        "ship_fee": ship_fee,
                        "total": total,
                        "point_saved": point_saved,
                        "ordered_at": ordered_at,
                    },
                ).scalar()

                for book in items:
                    self.db.execute(
                        text(
                            """
                            INSERT INTO shop.order_items
                                (order_id, book_id, book_title, unit_price, quantity,
                                 item_discount, item_total, status, created_at)
                            SELECT :order_id, b.book_id, b.title, b.sale_price, :qty,
                                   0, b.sale_price * :qty, CAST(:status AS shop.order_status), :ordered_at
                              FROM shop.books b WHERE b.book_id = :book_id
                            """
                        ),
                        {
                            "order_id": order_id,
                            "book_id": book["book_id"],
                            "qty": book["_qty"],
                            "status": status,
                            "ordered_at": ordered_at,
                        },
                    )
                    item_count += 1

# 구매 확정 건의 약 45%가 리뷰 작성
# 구매 확정 주문 중 약 45%를 리뷰 작성 후보로 추가한다.
                    if status == "CONFIRMED" and random.random() < 0.45:
                        review_rows.append(
                            {
                                "book_id": book["book_id"],
                                "member_id": member_id,
                                "created_at": ordered_at + timedelta(days=random.randint(3, 20)),
                            }
                        )

                # 결제 / 배송
                self.db.execute(
                    text(
                        """

                        INSERT INTO shop.payments
                            (order_id, pg_provider, pg_tid, method, status, amount,
                             card_name, card_no_masked, requested_at, approved_at)
                        VALUES (:order_id, 'INICIS', :tid, CAST(:method AS shop.payment_method),
                                CAST(:pstatus AS shop.payment_status), :amount,
                                '모의카드', '5555-****-****-1234', :ordered_at,
                                CASE WHEN :pstatus = 'PAID' THEN :ordered_at END)
                        """
                    ),
                    {
                        "order_id": order_id,
                        "tid": f"MOCK{random.randint(10**11, 10**12 - 1)}",
                        "method": random.choice(methods),
# 취소 주문은 취소, 대기 주문은 READY, 그 외 주문은 PAID 결제 상태로 기록한다.
                        "pstatus": "CANCELLED" if status == "CANCELLED" else ("READY" if status == "PENDING" else "PAID"),
                        "amount": total,
                        "ordered_at": ordered_at,
                    },
                )

# 배송 중·배송 완료·구매 확정이면 운송장 정보를 저장한다.
                if status in ("SHIPPING", "DELIVERED", "CONFIRMED"):
                    self.db.execute(
                        text(
                            """
                            INSERT INTO shop.shipments
                                (order_id, carrier_code, carrier_name, invoice_no, status,
                                 ship_fee, shipped_at, delivered_at, created_at)
                            VALUES (:order_id, 'CJ', 'CJ대한통운', :invoice,
                                    CAST(:sstatus AS shop.shipment_status), :ship_fee,
                                    :ordered_at + interval '1 day',
                                    CASE WHEN :sstatus = 'DELIVERED'
                                         THEN :ordered_at + interval '2 days' END,
                                    :ordered_at)
                            """
                        ),
                        {
                            "order_id": order_id,
                            "invoice": str(random.randint(10**11, 10**12 - 1)),
                            "sstatus": "IN_TRANSIT" if status == "SHIPPING" else "DELIVERED",
                            "ship_fee": ship_fee,
                            "ordered_at": ordered_at,
                        },
                    )
                    
# 발송 전인 주문은 송장 없이 배송 준비 상태로 저장한다.
# 나머지 확률로 낮은 평점과 부정 리뷰를 고른다.
                else:
                    self.db.execute(
                        text(
                            """
                            INSERT INTO shop.shipments (order_id, status, ship_fee, created_at)
                            VALUES (:order_id, 'READY', :ship_fee, :ordered_at)
                            """
                        ),
                        {"order_id": order_id, "ship_fee": ship_fee, "ordered_at": ordered_at},
                    )
                order_count += 1

# 주문 200건마다 중간 저장한다.
            if order_count % 200 == 0:
                self.db.commit()
        self.db.commit()
        print(f"  주문 {order_count}건 / 주문상품 {item_count}건 생성")
        
# 주문 생성이 끝난 뒤 모아둔 리뷰 후보로 리뷰를 만든다.
        self.create_reviews(review_rows)


# ------------------------------------------------------------------ 리뷰
# 평점과 어울리는 내용의 가상 리뷰를 만든다.
    def create_reviews(self, candidates: list[dict]) -> None:
        
# 회원 한 명이 같은 책에 리뷰를 중복 작성하지 않도록 기록한다.
        seen = set()
        created = 0
        for row in candidates:
            
# 책 번호와 회원 번호를 묶어 중복 확인용 키를 만든다.
            key = (row["book_id"], row["member_id"])
            if key in seen:
                continue
            seen.add(key)

# 무작위 숫자로 긍정·중립·부정 리뷰 비율을 결정한다.
            dice = random.random()
            
# 62% 확률로 높은 평점과 긍정 리뷰를 고른다.
            if dice < 0.62:
                rating = random.choice([5, 5, 4])
                content = random.choice(POSITIVE_TEMPLATES)
                
# 다음 22% 확률로 보통 평점과 중립 리뷰를 고른다.
            elif dice < 0.84:
                rating = 3
                content = random.choice(NEUTRAL_TEMPLATES)
            else:
                rating = random.choice([2, 1])
                content = random.choice(NEGATIVE_TEMPLATES)

            self.db.execute(
                text(
                    """

                    INSERT INTO shop.reviews
                        (book_id, member_id, rating, title, content, like_count, created_at)
                    VALUES (:book_id, :member_id, :rating, NULL, :content, :likes, :created_at)
                    """
                ),
                {
                    **row,
                    "rating": rating,
                    "content": content,
                    "likes": random.randint(0, 40),
                },
            )
            created += 1

        self.db.commit()
        print(f"  리뷰 {created}건 생성")


# ------------------------------------------------- 조회/위시리스트/문의
# 최근 본 책, 위시리스트, 검색 기록을 만든다.
    def create_behavior_logs(self) -> None:
        views = 0
        wishes = 0
        now = datetime.now(KST)
        
        for member_id in self.member_ids:
            
# 회원마다 0~25건의 책 조회 기록을 만든다.
            for _ in range(random.randint(0, 25)):
                book = random.choice(self.pick_books(member_id, 1) or self.books)
                self.db.execute(
                    text(
                        """
                        INSERT INTO log.recent_views (member_id, book_id, dwell_seconds, created_at)
                        VALUES (:m, :b, :d, :c)
                        """
                    ),
                    {
                        "m": member_id,
                        "b": book["book_id"],
                        "d": random.randint(5, 400),
                        "c": now - timedelta(days=random.randint(0, 80), hours=random.randint(0, 23)),
                    },
                )
                views += 1

# 회원마다 관심 책을 0~3권 위시리스트에 넣는다.
            for book in self.pick_books(member_id, random.randint(0, 3)):
                self.db.execute(
                    text(
                        """
                        INSERT INTO shop.wishlists (member_id, book_id, created_at)

                        VALUES (:m, :b, :c) ON CONFLICT DO NOTHING
                        """
                    ),
                    {"m": member_id, "b": book["book_id"], "c": now - timedelta(days=random.randint(0, 120))},
                )
                wishes += 1

# 검색 기록에 쓸 가상 검색어 목록이다.
        keywords = ["파이썬", "소설", "자기계발", "FastAPI", "Vue", "한강", "김영하",
                    "머신러닝", "클린 코드", "데이터 분석", "에세이", "추리소설"]
        
# 전체 회원이 남긴 검색 기록 500건을 만든다.
        for _ in range(500):
            self.db.execute(
                text(
                    """
                    INSERT INTO log.search_logs (member_id, keyword, result_count, created_at)
                    VALUES (:m, :k, :c, :t)
                    """
                ),
                {
                    "m": random.choice(self.member_ids),
                    "k": random.choice(keywords),
                    "c": random.randint(0, 30),
                    "t": now - timedelta(days=random.randint(0, 14), hours=random.randint(0, 23)),
                },
            )

        self.db.commit()
        print(f"  조회 이력 {views}건 / 위시리스트 {wishes}건 / 검색 로그 500건 생성")

# Q&A와 고객센터 1:1 상담 데이터를 만든다.
    def create_support_data(self) -> None:
        
# 문의 게시판 글 40건을 만든다.
        for _ in range(40):
            category, title, content = random.choice(QNA_SAMPLES)
            member_id = random.choice(self.member_ids)
# 약 70%의 문의에 답변이 달리도록 정한다.
            answered = random.random() < 0.7
            question_id = self.db.execute(
                text(
                    """
                    INSERT INTO shop.qna_questions
                        (member_id, category, title, content, status, is_secret, view_count, created_at)
                    VALUES (:m, :cat, :title, :content,
                            CAST(:status AS shop.qna_status), :secret, :views,
                            now() - (:days || ' days')::interval)

                    RETURNING question_id
                    """
                ),
                {
                    "m": member_id,
                    "cat": category,
                    "title": title,
                    "content": content,
                    "status": "ANSWERED" if answered else "WAITING",
                    "secret": random.random() < 0.25,
                    "views": random.randint(0, 80),
                    "days": random.randint(0, 120),
                },
            ).scalar()

# 답변이 있다고 정한 질문에 답변 정보를 추가한다.
            if answered:
                self.db.execute(
                    text(
                        """
                        INSERT INTO shop.qna_answers (question_id, admin_id, content, created_at)

                        SELECT :qid, m.member_id,
                               '문의해 주셔서 감사합니다. 확인 결과를 안내드립니다. 추가 문의는 1:1 상담을 이용해 주세요.',
                               now() - (:days || ' days')::interval
                          FROM shop.members m WHERE m.role = 'ADMIN' LIMIT 1
                        """
                    ),
                    {"qid": question_id, "days": random.randint(0, 100)},
                )

# 1:1 상담방 25개를 만든다.
        for _ in range(25):
            member_id = random.choice(self.member_ids)
            
# 상담방의 약 60%를 종료 상태로 정한다.
            closed = random.random() < 0.6
            room_id = self.db.execute(
                text(
                    """
                    INSERT INTO shop.chat_rooms
                        (member_id, subject, status, last_message, last_message_at,
                         satisfaction, created_at, closed_at)
                    VALUES (:m, '1:1 문의', CAST(:status AS shop.chat_room_status), :msg,
                            now() - (:days || ' days')::interval,
                            CASE WHEN :closed THEN :score END,
                            now() - (:days || ' days')::interval,
                            CASE WHEN :closed THEN now() - (:days || ' days')::interval + interval '1 hour' END)
                    RETURNING room_id
                    """
                ),
                {
                    "m": member_id,
                    "status": "CLOSED" if closed else random.choice(["OPEN", "ASSIGNED"]),
                    "msg": random.choice(CHAT_SAMPLES),
                    "days": random.randint(0, 90),
                    "closed": closed,
                    "score": random.randint(3, 5),
                },
            ).scalar()

            self.db.execute(
                text(
                    """
                    INSERT INTO shop.chat_messages (room_id, sender_id, sender_type, content, is_read, created_at)
                    VALUES (:r, NULL, 'SYSTEM',
                            '안녕하세요, 북스토어 고객센터입니다. 문의 내용을 남겨 주세요.', true,
                            now() - (:days || ' days')::interval),
                           (:r, :m, 'USER', :msg, true, now() - (:days || ' days')::interval)
                    """
                ),
                {"r": room_id, "m": member_id, "msg": random.choice(CHAT_SAMPLES), "days": random.randint(0, 90)},
            )

        self.db.commit()
        print("  Q&A 40건 / 상담 25건 생성")


# ------------------------------------------------------------------ 보정
# 판매량·평점·회원 구매액·회원 등급을 다시 계산한다.
    def refresh_aggregates(self) -> None:
        """도서 판매량/평점, 회원 등급/누적 구매액을 실제 데이터로 재계산한다."""
        self.db.execute(
            text(
                """
                UPDATE shop.books b SET sales_count = COALESCE(s.qty, 0)
                  FROM (SELECT oi.book_id, SUM(oi.quantity)::int AS qty
                          FROM shop.order_items oi
                          JOIN shop.orders o ON o.order_id = oi.order_id
                         WHERE o.status IN ('PAID','PREPARING','SHIPPING','DELIVERED','CONFIRMED')
                         GROUP BY oi.book_id) s
                 WHERE b.book_id = s.book_id
                """
            )
        )
        self.db.execute(
            text(
                """
                UPDATE shop.books b
                   SET rating_avg = COALESCE(r.avg_rating, 0), review_count = COALESCE(r.cnt, 0)
                  FROM (SELECT book_id, ROUND(AVG(rating)::numeric, 2) AS avg_rating, COUNT(*) AS cnt
                          FROM shop.reviews WHERE is_blinded = false GROUP BY book_id) r
                 WHERE b.book_id = r.book_id
                """
            )
        )
        self.db.execute(
            text(
                """
                UPDATE shop.members m
                   SET total_paid = COALESCE(o.amount, 0), order_count = COALESCE(o.cnt, 0)
                  FROM (SELECT member_id, SUM(total_amount) AS amount, COUNT(*) AS cnt
                          FROM shop.orders
                         WHERE status IN ('PAID','PREPARING','SHIPPING','DELIVERED','CONFIRMED')
                         GROUP BY member_id) o
                 WHERE m.member_id = o.member_id
                """
            )
        )
        member_ids = [r[0] for r in self.db.execute(text("SELECT member_id FROM shop.members"))]
        for mid in member_ids:
            
# DB에 정의된 함수로 회원 등급을 한 명씩 갱신한다.
            self.db.execute(text("SELECT shop.fn_refresh_member_grade(:m)"), {"m": mid})
        self.db.commit()
        print("  집계 컬럼(판매량/평점/등급) 재계산 완료")
        
        
# ------------------------------------------------------------------ 실행
# 전체 데이터 생성 작업을 정해진 순서대로 부르는 함수다.
    def run(self) -> None:
        print("데모 데이터 생성 시작")

        self.load_books()               # 먼저 도서 목록을 읽는다.
        self.create_members()           # 관리자와 일반 회원을 만든다.
        self.create_orders()            # 주문·결제·배송과 리뷰를 만든다.
        self.create_behavior_logs()     # 조회·위시리스트·검색 기록을 만든다.
        self.create_support_data()      # Q&A와 상담 기록을 만든다.
        self.refresh_aggregates()       # 만든 데이터에 맞게 통계와 회원 등급을 갱신한다.
        print("데모 데이터 생성 완료")


# 실행 옵션을 읽고 생성 작업을 시작하는 프로그램 진입점이다.
def main() -> None:
# 명령 프롬프트 옵션을 읽는 도구를 만든다.
    parser = argparse.ArgumentParser(description="북스토어 데모 데이터 생성")
    
# 생성할 회원 수다. 기본값은 300명이다.
    parser.add_argument("--members", type=int, default=300, help="생성할 회원 수")
    
# 데이터를 퍼뜨릴 과거 기간이다. 기본값은 365일이다.
    parser.add_argument("--days", type=int, default=365, help="데이터 생성 기간(일)")
    
# 무작위 결과를 재현할 숫자다. 같은 값이면 같은 순서의 난수 결과를 만든다.
    parser.add_argument("--seed", type=int, default=42, help="난수 시드")
    
# 붙이면 데이터 생성 뒤 AI 모델 학습까지 실행한다.
    parser.add_argument("--train", action="store_true", help="생성 후 AI 모델까지 학습")
    
# 사용자가 명령 프롬프트에 적은 옵션을 읽어 저장한다.
    args = parser.parse_args()

# DB 연결을 여는 세션을 만든다.
    db = SessionLocal()
    
# 작업 중 오류가 나도 마지막에 DB 연결을 닫을 수 있게 한다.
    try:
        
# 입력한 옵션으로 생성기를 만들고 작업을 실행한다.
        DemoDataGenerator(db, args.members, args.days, args.seed).run()

# --train 옵션을 준 경우에만 학습을 진행한다.
        if args.train:
            
# AI 학습 실행에 필요한 코드를 불러온다.
            from team_backend.app.ai.pipeline import AiPipeline
            print("\nAI 모델 학습 시작")
            
# 등록된 AI 모델 학습 작업을 실행한다.
            results = AiPipeline(db).run_all()
            for name, result in results.items():
                print(f"  {name}: {result}")
            print("AI 모델 학습 완료")
            
# 작업이 성공하거나 오류가 나도 아래 정리 코드를 실행한다.
    finally:
        db.close()      # DB 세션을 닫아 연결 자원을 돌려준다.


# 이 파일을 직접 실행했을 때만 main()을 시작한다.

if __name__ == "__main__":
    main()