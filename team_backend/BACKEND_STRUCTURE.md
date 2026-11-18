# 북적북적 백엔드 구조 및 REST API 설계서

## 1. 설계 범위

이 문서는 `backend/app/main.py`에서 실행하는 FastAPI 앱의 현재 구조와 API 계약을 기록한다. PostgreSQL 연결과 조회·저장은 SQLAlchemy가 담당하고, 요청과 응답의 형식은 Pydantic 모델로 정의한다. 설치 방법과 화면 메뉴는 [README.md](README.md)를 참고한다.

## 2. 백엔드 파일 구조

```text
backend/
├── app/
│   ├── main.py                 # FastAPI 앱, 미들웨어, 예외 처리, 라우터 등록
│   ├── core/
│   │   ├── config.py           # 환경 변수와 앱 설정
│   │   ├── database.py         # PostgreSQL 엔진, Base, 요청별 DB 세션
│   │   ├── security.py         # 비밀번호, JWT, 회원 및 관리자 권한
│   │   ├── exceptions.py       # 업무 예외와 공통 오류 응답
│   │   └── logging_config.py   # 콘솔 및 파일 로깅
│   ├── routers/
│   │   ├── __init__.py         # 현재 앱에 등록되는 라우터와 API 접두사
│   │   ├── auth.py, members.py  # 인증 및 회원 기능
│   │   ├── books.py, cart.py, orders.py, reviews.py
│   │   ├── support.py, chat.py  # 공지·FAQ·문의·상담 및 WebSocket
│   │   ├── admin.py, ai_router.py
│   │   ├── pages.py            # 서버 렌더링 페이지 라우트
│   │   └── payments_router.py  # 별도 결제 라우터 파일, 현재 앱 등록 제외
│   ├── schemas/               # 도서·회원·주문·리뷰·고객지원·AI·공통 모델
│   ├── models/                # 도서·회원·장바구니·주문·리뷰·프로모션 등 ORM
│   ├── services/              # 인증·주문·결제·배송·고객지원 등의 처리 로직
│   ├── ai/                    # 추천·감성 분석·판매/고객 분석·배치
│   └── static/                # 앱 로드 시 준비하는 정적 파일 디렉터리
├── database/
│   ├── schema.sql             # 신규 DB의 스키마·테이블·인덱스
│   └── seed_master.sql        # 기본 데이터
├── scripts/generate_demo_data.py
├── .env.example
├── requirements.txt
├── README.md
└── BACKEND_STRUCTURE.md
```

### 요청 처리 흐름

1. `app/main.py`가 앱과 미들웨어를 구성하고, `routers/__init__.py`가 기능 라우터를 등록한다.
2. FastAPI가 본문·경로·쿼리 값을 검증하고, 의존성에서 DB 세션과 회원 정보를 준비한다. 관리자 기능은 회원 권한까지 확인한다.
3. 라우터와 서비스가 DB 세션을 사용해 처리하고, 선언된 응답 모델 또는 해당 라우트의 응답 형식으로 반환한다. 예외는 `core/exceptions.py`에 등록된 핸들러에서 처리한다.

### 데이터베이스 구성

| PostgreSQL 스키마 | 역할 |
| --- | --- |
| `shop` | 회원·주소·도서·카테고리·장바구니·주문·결제·배송·리뷰·쿠폰·고객지원 |
| `ai` | 추천·도서 유사도·리뷰 감성·매출 집계·예측·고객 세그먼트·이탈 예측·실행 이력 |
| `log` | 로그인·재고·검색·최근 조회·결제 이력 |

`Coupon`, `MemberCoupon`, `Banner`는 [promotion.py](app/models/promotion.py)에 정의한다. 공지·첨부파일·문의·답변·FAQ·상담방·메시지는 [support.py](app/models/support.py)에 정의한다. 신규 개발 DB 구성은 [schema.sql](database/schema.sql)과 [seed_master.sql](database/seed_master.sql)을 기준으로 한다.

## 3. 기존 REST API 설계 대비 변경점

| 기존 설계 | 현재 등록된 메서드와 경로 | 요청 → 응답 |
| --- | --- | --- |
| `/api/auth/signup` | `POST /api/v1/auth/signup` | `SignupRequest` → `MemberResponse` (201) |
| `/api/auth/login` | `POST /api/v1/auth/login` | `LoginRequest` → `TokenResponse` |
| `/api/auth/refresh` | `POST /api/v1/auth/refresh` | `RefreshRequest` → `TokenResponse` |
| `/api/auth/me` | `GET /api/v1/auth/me` | 로그인 회원 → `MemberResponse` |
| `/api/products`, `/api/products/{product_id}` | `GET /api/v1/books`, `GET /api/v1/books/{book_id}` | `PageResponse[BookListItem]`, `BookDetailResponse` |
| 상품 등록 요청 | `POST /api/v1/admin/books` | `BookCreateRequest` → `BookDetailResponse` (201) |
| `/api/cart`, `/api/cart/{cart_item_id}` | `GET /api/v1/cart`, `POST /api/v1/cart/items`, `PUT`·`DELETE /api/v1/cart/items/{cart_item_id}` | 추가는 `CartItemAddRequest`, 수정은 `CartItemUpdateRequest`. 응답은 `CartResponse` |
| `/api/orders`, `/api/orders/{order_id}` | `POST`·`GET /api/v1/orders`, `GET /api/v1/orders/{order_id}` | 생성은 `OrderCreateRequest` → `OrderResponse` (200), 목록은 `PageResponse[OrderResponse]` |
| `/api/ai/recommendations` | `GET /api/v1/ai/recommendations` | `limit`, `algorithm` → `RecommendationResponse` |
| `/api/ai/reviews/{product_id}/sentiment` | 도서별 `GET /api/v1/books/{book_id}/review-stats`, 텍스트 분석 `POST /api/v1/reviews/analyze-sentiment` | 도서 리뷰 통계는 `ReviewStatsResponse`, 입력한 텍스트 분석은 `SentimentAnalyzeRequest`의 `text` 사용 |
| `/api/admin/dashboard/stats`, `/api/admin/dashboard/analytics` | `GET /api/v1/admin/dashboard`, `GET /api/v1/ai/sales/summary`, `GET /api/v1/ai/customers/analysis` | `DashboardResponse`, `SalesSummaryResponse`, `CustomerAnalysisResponse` |

## 4. 메서드·매개변수·요청 및 응답

- **HTTP 메서드**는 현재 `GET`, `POST`, `PUT`, `DELETE`가 등록돼 있습니다. 장바구니 수량과 선택 상태는 `PUT` 요청에서 전달된 항목만 바꿀 수 있습니다.
- **경로 매개변수**인 `book_id`, `cart_item_id`, `order_id`는 정수입니다. 상품 번호를 전달하던 자리는 현재 도서 번호인 `book_id`를 사용합니다.
- **페이지네이션**은 `page`, `size`로 받고 SQLAlchemy에서 `offset((page - 1) * size).limit(size)` 방식으로 조회합니다. 도서 목록은 기본 `page=1`, `size=20`이며 `size`의 범위는 1~100입니다. 도서 리뷰 목록은 기본 `size=10`입니다. `PageResponse[T]`는 `success`, `items`, `meta`를 반환하며 `meta`에는 `page`, `size`, `total`, `total_pages`가 있습니다.
- **정렬과 검색**에서 도서 목록은 `sort_by`·`direction` 대신 `sort` 하나를 사용합니다. 선택값은 `recent`(기본), `sales`, `price_asc`, `price_desc`, `rating`, `review`, `title`입니다. `keyword`로 도서를 검색하고 `category_id`, `publisher_id`, `author_id`, 가격 범위, 국내 도서 여부, 재고 여부로 결과를 좁힐 수 있습니다.
- **요청 본문**의 필드 이름은 `snake_case`입니다. 회원가입 필수 항목은 `email`, `password`, `password_confirm`, `name`입니다. 도서 등록은 `isbn13`, `title`, `category_id`, `publisher_id`, `list_price`, `sale_price` 등을 사용합니다. 장바구니 추가는 `book_id`, `quantity`를 받습니다. 주문 생성은 주문자 정보와 `receiver`, `receiver_phone`, `zipcode`, `address1` 등 배송지 정보를 받고, `items`를 생략하면 장바구니에서 선택한 항목을 사용합니다. `payment_method`로 결제 수단을 선택하고 실제 결제 요청은 주문 생성 후 `POST /orders/{order_id}/pay`로 진행합니다.
- **인증**은 회원 API에서 FastAPI 의존성으로 확인합니다. HTTP 요청의 `Authorization: Bearer <access_token>` 또는 `access_token` 쿠키를 사용할 수 있습니다. 관리자 API는 `require_admin`, 일부 작업은 `require_superadmin`을 사용합니다. 비회원도 장바구니와 주문 생성에 접근할 수 있으며, 비회원 주문 조회에는 주문번호와 이메일이 필요합니다.

[공통 응답 모델](app/schemas/common.py) · [도서 쿼리](app/routers/books.py) · [도서 조회 로직](app/services/book_service.py) · [회원 요청 모델](app/schemas/member.py) · [도서 요청 모델](app/schemas/book.py) · [장바구니·주문 요청 모델](app/schemas/order.py) · [인증 코드](app/core/security.py)

## 5. 상태 코드 및 오류 응답

| HTTP 상태 | 현재 처리 |
| --- | --- |
| `200 OK` | 일반 성공. 주문 생성 등 일부 POST 요청도 200을 반환 |
| `201 Created` | 회원가입, 리뷰 작성, 문의 등록, 채팅방 생성, 관리자 도서·공지 등록 |
| `400 Bad Request` | 업무 규칙 위반. 기본 `BUSINESS_ERROR`, 가입 이메일 중복은 `EMAIL_DUPLICATED` |
| `401 Unauthorized` | 인증 실패. HTTP 예외는 `HTTP_401`, 잘못된 로그인 정보는 `INVALID_CREDENTIALS` |
| `403 Forbidden` | 권한 부족. HTTP 예외는 `HTTP_403`, 업무 예외 유형에 따라 `FORBIDDEN` 등 |
| `404 Not Found` | 리소스를 찾지 못함. 업무 예외는 `NOT_FOUND`, HTTP 예외는 `HTTP_404` |
| `409 Conflict` | DB 제약 조건 위반 `DB_CONFLICT` |
| `422 Unprocessable Entity` | Pydantic 요청 검증 실패 `VALIDATION_ERROR` |
| `500 Internal Server Error` | DB 처리 오류 `DB_ERROR`, 예상하지 못한 오류 `INTERNAL_ERROR` |

실행 중 오류 응답은 `{"success": false, "error": {"code": "NOT_FOUND", "message": "도서를 찾을 수 없습니다."}}` 형태입니다. 검증 실패 시 `error.detail`에 항목별 오류를 포함할 수 있습니다. `OUT_OF_STOCK`과 `PAYMENT_FAILED`도 예외 클래스로 정의돼 있으며, 실제 응답 코드는 각 서비스가 발생시킨 예외에 따릅니다. 프런트엔드에서 분기할 때는 설계서의 리소스별 예시 코드보다 현재 API의 `error.code`를 기준으로 확인합니다. [예외 처리](app/core/exceptions.py) · [인증 서비스](app/services/auth_service.py)

## 6. AI 모델과 처리 방식

AI 로직은 `app/ai/`에 있습니다. 관리자 API에서 학습·재계산 작업을 시작할 수 있고, 일부 API는 요청 시에도 계산합니다. 배치 파이프라인은 구현돼 있으며, 매일 밤 실행하는 자동 스케줄은 현재 백엔드 소스에서 확인되지 않았습니다.

| 기능 | 현재 구현 | 관련 DB 테이블 |
| --- | --- | --- |
| 맞춤 추천 | 협업 필터링과 도서 정보 기반 추천. 추천 API가 요청 시 추천기를 통해 결과를 계산하고 배치도 결과를 저장할 수 있음 | `ai.recommendations`, `ai.book_similarities` |
| 리뷰 감성분석 | 한국어 어휘 규칙과 학습된 로지스틱 회귀 모델 활용. 리뷰 작성·수정과 텍스트 분석 요청에서도 실행 | `ai.review_sentiments` |
| 고객 세그먼트 | 최근 구매일·구매 빈도·구매 금액을 이용한 RFM 점수화와 K-means 군집화 | `ai.customer_segments` |
| 이탈 예측 | 로지스틱 회귀 기반 위험도 예측 | `ai.churn_predictions` |
| 판매 분석 및 예측 | 일별 매출 집계, 미래 판매량 예측. 예측 API는 `retrain=true` 옵션 제공 | `ai.sales_daily`, `ai.sales_forecasts` |
| 실행 이력 | 학습·집계 파이프라인의 작업 결과 기록 | `ai.model_runs` |

[추천 모델](app/ai/recommender.py) · [감성 분석](app/ai/sentiment.py) · [고객 분석](app/ai/customer_analytics.py) · [배치 파이프라인](app/ai/pipeline.py) · [AI API](app/routers/ai_router.py)

## 7. 추가 등록 API 목록

아래 표의 경로 앞에는 기본 접두사 `/api/v1`을 붙입니다. 예를 들어 `GET /auth/check-email`의 전체 주소는 `GET /api/v1/auth/check-email`입니다. 같은 경로에 여러 메서드가 등록된 경우도 각각 표시했습니다.

- **공개**는 회원 로그인 의존성이 없는 경로입니다. 주문 조회처럼 요청 데이터 자체로 추가 확인을 하는 경로도 있습니다.
- **선택**은 로그인 없이 호출할 수 있고, 로그인 정보가 있으면 활용하는 경로입니다.
- **회원**, **관리자**, **최고 관리자**는 각각 해당 인증·권한이 필요합니다.

#### 인증·회원·쿠폰

| 메서드 | 경로 | 기능 | 접근 |
| --- | --- | --- | --- |
| `GET` | `/auth/check-email` | 이메일 중복 확인 | 공개 |
| `POST` | `/auth/logout` | 로그아웃 | 공개 |
| `PUT` | `/auth/password` | 비밀번호 변경 | 회원 |
| `POST` | `/auth/password/reset` | 임시 비밀번호 발급 | 공개 |
| `POST` | `/auth/withdraw` | 회원 탈퇴 | 회원 |
| `GET` | `/members/me` | 내 정보 | 회원 |
| `PUT` | `/members/me` | 내 정보 수정 | 회원 |
| `GET` | `/members/me/stats` | 마이페이지 요약 | 회원 |
| `GET` | `/members/me/addresses` | 배송지 목록 | 회원 |
| `POST` | `/members/me/addresses` | 배송지 등록 | 회원 |
| `PUT` | `/members/me/addresses/{address_id}` | 배송지 수정 | 회원 |
| `DELETE` | `/members/me/addresses/{address_id}` | 배송지 삭제 | 회원 |
| `GET` | `/members/me/points` | 포인트 내역 | 회원 |
| `GET` | `/members/me/coupons` | 보유 쿠폰 | 회원 |
| `POST` | `/members/me/coupons` | 쿠폰 코드 등록 | 회원 |
| `GET` | `/members/me/coupons/available` | 적용 가능 쿠폰 | 회원 |
| `GET` | `/members/me/reviews` | 내가 쓴 리뷰 | 회원 |
| `GET` | `/members/me/reviewable` | 리뷰 작성 가능 상품 | 회원 |
| `GET` | `/members/me/recommendations` | 내 맞춤 추천 도서 | 회원 |

#### 도서·리뷰

| 메서드 | 경로 | 기능 | 접근 |
| --- | --- | --- | --- |
| `GET` | `/books/categories` | 카테고리 트리 | 공개 |
| `GET` | `/books/bestsellers` | 베스트셀러 | 공개 |
| `GET` | `/books/new-releases` | 신간 목록 | 공개 |
| `GET` | `/books/popular-keywords` | 인기 검색어 | 공개 |
| `GET` | `/books/recent-views` | 최근 본 도서 | 선택 |
| `GET` | `/books/{book_id}/reviews` | 도서 리뷰 목록 | 선택 |
| `GET` | `/books/{book_id}/similar` | 유사 도서 추천 | 공개 |
| `GET` | `/books/{book_id}/bought-together` | 함께 구매한 도서 | 공개 |
| `POST` | `/reviews` | 리뷰 작성 | 회원 |
| `PUT` | `/reviews/{review_id}` | 리뷰 수정 | 회원 |
| `DELETE` | `/reviews/{review_id}` | 리뷰 삭제 | 회원 |
| `POST` | `/reviews/{review_id}/like` | 리뷰 도움됨 토글 | 회원 |

#### 장바구니·위시리스트·주문

| 메서드 | 경로 | 기능 | 접근 |
| --- | --- | --- | --- |
| `POST` | `/cart/items/bulk-delete` | 장바구니 선택 삭제 | 선택 |
| `POST` | `/cart/select-all` | 전체 선택/해제 | 선택 |
| `DELETE` | `/cart` | 장바구니 비우기 | 선택 |
| `GET` | `/wishlist` | 위시리스트 조회 | 회원 |
| `POST` | `/wishlist/{book_id}` | 위시리스트 토글 | 회원 |
| `GET` | `/orders/stats` | 내 주문 통계 | 회원 |
| `GET` | `/orders/lookup` | 비회원 주문 조회 | 공개 |
| `POST` | `/orders/{order_id}/pay` | 결제 요청 | 선택 |
| `POST` | `/orders/payments/callback` | PG 결제 콜백 | 공개 |
| `POST` | `/orders/{order_id}/cancel` | 주문 취소 | 회원 |
| `POST` | `/orders/{order_id}/confirm` | 구매 확정 | 회원 |
| `POST` | `/orders/{order_id}/return` | 반품 접수 | 회원 |
| `GET` | `/orders/{order_id}/shipment` | 배송 조회 | 회원 |
| `GET` | `/orders/{order_id}/tracking-url` | 택배사 조회 URL | 회원 |

#### 고객지원·채팅

| 메서드 | 경로 | 기능 | 접근 |
| --- | --- | --- | --- |
| `GET` | `/notices` | 공지 목록 | 공개 |
| `GET` | `/notices/{notice_id}` | 공지 상세 | 공개 |
| `GET` | `/notices/{notice_id}/adjacent` | 이전/다음 공지 | 공개 |
| `GET` | `/qna` | Q&A 목록 | 선택 |
| `POST` | `/qna` | 문의 등록 | 회원 |
| `GET` | `/qna/{question_id}` | 문의 상세 | 선택 |
| `DELETE` | `/qna/{question_id}` | 문의 삭제 | 회원 |
| `GET` | `/faqs` | FAQ 목록 | 공개 |
| `GET` | `/faqs/categories` | FAQ 카테고리 | 공개 |
| `POST` | `/faqs` | FAQ 등록(관리자) | 관리자 |
| `DELETE` | `/faqs/{faq_id}` | FAQ 삭제(관리자) | 관리자 |
| `POST` | `/chat/rooms` | 상담 시작 | 회원 |
| `GET` | `/chat/rooms` | 내 상담 목록 | 회원 |
| `GET` | `/chat/rooms/{room_id}` | 상담 상세 | 회원 |
| `GET` | `/chat/rooms/{room_id}/messages` | 메시지 조회 | 회원 |
| `POST` | `/chat/rooms/{room_id}/messages` | 메시지 전송(REST) | 회원 |
| `POST` | `/chat/rooms/{room_id}/close` | 상담 종료 | 회원 |
| `POST` | `/chat/rooms/{room_id}/satisfaction` | 상담 만족도 평가 | 회원 |

#### AI·분석

| 메서드 | 경로 | 기능 | 접근 |
| --- | --- | --- | --- |
| `GET` | `/ai/sales/monthly` | 월별 매출 | 관리자 |
| `GET` | `/ai/sales/categories` | 카테고리별 매출 | 관리자 |
| `GET` | `/ai/sales/best-sellers` | 기간 베스트셀러 | 관리자 |
| `GET` | `/ai/sales/forecast` | 판매 예측 | 관리자 |
| `GET` | `/ai/sales/distribution` | 주문 시간/요일 분포 | 관리자 |
| `GET` | `/ai/customers/purchase-analysis` | 구매 분석 | 관리자 |
| `GET` | `/ai/customers/churn` | 이탈 예측 결과 | 관리자 |
| `GET` | `/ai/customers/churn/feature-importance` | 이탈 예측 피처 중요도 | 관리자 |
| `POST` | `/ai/train/{model_name}` | AI 모델 학습 실행 | 관리자 |
| `GET` | `/ai/model-runs` | 모델 실행 이력 | 관리자 |

#### 관리자

| 메서드 | 경로 | 기능 | 접근 |
| --- | --- | --- | --- |
| `GET` | `/admin/dashboard/alerts` | 운영 알림 | 관리자 |
| `GET` | `/admin/books` | 도서 목록(관리자) | 관리자 |
| `PUT` | `/admin/books/{book_id}` | 도서 수정 | 관리자 |
| `DELETE` | `/admin/books/{book_id}` | 도서 삭제 | 관리자 |
| `POST` | `/admin/books/{book_id}/stock` | 재고 조정 | 관리자 |
| `GET` | `/admin/books/low-stock` | 재고 부족 도서 | 관리자 |
| `GET` | `/admin/books/{book_id}/stock-history` | 재고 변동 이력 | 관리자 |
| `GET` | `/admin/orders` | 주문 목록(관리자) | 관리자 |
| `GET` | `/admin/orders/{order_id}` | 주문 상세(관리자) | 관리자 |
| `PUT` | `/admin/orders/{order_id}/status` | 주문 상태 변경 | 관리자 |
| `POST` | `/admin/orders/{order_id}/cancel` | 주문 강제 취소 | 관리자 |
| `POST` | `/admin/orders/{order_id}/refund` | 결제 환불 | 관리자 |
| `GET` | `/admin/members` | 회원 목록 | 관리자 |
| `GET` | `/admin/members/{member_id}` | 회원 상세 | 관리자 |
| `PUT` | `/admin/members/{member_id}/status` | 회원 상태 변경 | 최고 관리자 |
| `POST` | `/admin/members/{member_id}/points` | 포인트 수동 조정 | 관리자 |
| `POST` | `/admin/batch/{job_name}` | 운영 배치 실행 | 최고 관리자 |
| `POST` | `/admin/shipments/{order_id}/invoice` | 송장 등록 | 관리자 |
| `POST` | `/admin/shipments/bulk-invoice` | 송장 일괄 등록 | 관리자 |
| `POST` | `/admin/shipments/{order_id}/tracking` | 배송 이력 추가 | 관리자 |
| `POST` | `/admin/shipments/{order_id}/simulate` | 배송 진행 시뮬레이션 | 관리자 |
| `GET` | `/admin/shipments/pending` | 발송 대기 목록 | 관리자 |
| `GET` | `/admin/shipments/stats` | 배송 상태 통계 | 관리자 |
| `POST` | `/admin/reviews/{review_id}/reply` | 리뷰 답글 등록 | 관리자 |
| `POST` | `/admin/reviews/{review_id}/blind` | 리뷰 블라인드 | 관리자 |
| `POST` | `/admin/reviews/mark-best` | 베스트 리뷰 선정 | 관리자 |
| `GET` | `/admin/notices` | 공지 목록(관리자) | 관리자 |
| `POST` | `/admin/notices` | 공지 등록 | 관리자 |
| `PUT` | `/admin/notices/{notice_id}` | 공지 수정 | 관리자 |
| `DELETE` | `/admin/notices/{notice_id}` | 공지 삭제 | 관리자 |
| `POST` | `/admin/qna/{question_id}/answer` | 답변 등록 | 관리자 |
| `POST` | `/admin/qna/{question_id}/close` | 문의 종료 | 관리자 |
| `GET` | `/admin/qna/waiting-count` | 미답변 건수 | 관리자 |
| `GET` | `/admin/chat/rooms` | 상담 목록 | 관리자 |
| `POST` | `/admin/chat/rooms/{room_id}/assign` | 상담원 배정 | 관리자 |
| `GET` | `/admin/chat/stats` | 상담 통계 | 관리자 |

#### 시스템

| 메서드 | 경로 | 기능 | 접근 |
| --- | --- | --- | --- |
| `GET` | `/health` | 헬스 체크(API) | 공개 |

## 8. WebSocket 및 별도 경로

- 실시간 상담은 `/api/v1/chat/ws/{room_id}`에 WebSocket으로 연결합니다. HTTP 방식의 채팅 메시지 조회·전송은 위 채팅 표를 참고하세요.
- 서버 상태 확인은 위 표의 `GET /api/v1/health`와 별도 경로인 `GET /health`를 모두 사용할 수 있습니다.
- `app/routers/payments_router.py`의 `/api/payments` 라우터는 현재 앱에 등록되어 있지 않습니다. 등록된 결제 API는 위 주문 표의 경로를 사용합니다.
- 검색·도서 상세·공지·FAQ·관리 화면 등 서버 렌더링 페이지는 [페이지 라우터](app/routers/pages.py)에서 제공합니다.

## 9. 주문·결제 처리 흐름

1. `POST /api/v1/orders`가 주문 항목을 확정한다. 서버에서 판매 상태·재고와 금액을 확인하고 주문·항목을 저장한다. 재고 차감과 선택한 장바구니 항목 반영은 주문 생성 트랜잭션에서 처리한다.
2. `POST /api/v1/orders/{order_id}/pay`에서 별도로 결제를 요청한다. 게이트웨이는 `PG_MOCK_MODE` 설정에 따라 모의 처리 또는 결제 제공자 구현을 선택한다. `POST /api/v1/orders/payments/callback`도 주문 라우터에 등록돼 있다.
3. 회원은 주문 상세와 배송 상태를 확인한다. 비회원은 `GET /api/v1/orders/lookup`에 주문번호와 이메일을 보낸다. 취소·반품·구매 확정과 관리자 송장·환불은 각각 별도 API다.

주문 생성 본문 예시는 다음과 같다. `book_id`는 개발 DB에 등록된 도서 번호를 사용한다.

```json
{
  "items": [{"book_id": 1, "quantity": 2}],
  "orderer_name": "홍길동",
  "orderer_phone": "010-1234-5678",
  "orderer_email": "reader@example.com",
  "receiver": "홍길동",
  "receiver_phone": "010-1234-5678",
  "zipcode": "04524",
  "address1": "서울시 예시로 1",
  "payment_method": "CARD"
}
```

[주문 서비스](app/services/order_service.py) · [결제 라우트](app/routers/orders.py) · [결제 게이트웨이](app/services/payment_gateway.py)

## 10. 실행과 통합 검증

`backend` 폴더에서 기존 `dl` 가상환경을 사용해 실행한다.

```cmd
..\dl\Scripts\python.exe -m uvicorn team_backend.app.main:app --reload
```

- [Swagger UI](http://127.0.0.1:8000/docs)와 [OpenAPI JSON](http://127.0.0.1:8000/openapi.json)에서 요청·응답 정의를 확인한다. [헬스 체크](http://127.0.0.1:8000/health) 응답의 `database`가 `connected`이면 앱의 DB 접속 확인을 통과한 상태다.
- [결제 테스트 파일](tests/test_payment_flow.py)은 현재 구조에서 사라진 `app.models.order_model`, `app.auth.jwt_tokens` 등의 경로를 참조한다. 기존 테스트를 현재 서비스와 라우터에 맞춰 갱신해야 한다.
- 신규 DB는 `database/schema.sql`을 기준으로 초기화한다. 이전 백엔드의 SQL 변경 이력은 [별도 보관 폴더](../legacy_backend/migrations/)에서 확인할 수 있다.
- Vue 화면은 별도 프로젝트의 `/shop/...` 계약을 사용한다. 이 앱의 `/api/v1/...`에 연결하려면 API 경로, 인증, 요청·응답 형식을 맞춰야 한다. [Vue 메뉴와 연동 항목](README.md#북스토어-메뉴-구조도)

