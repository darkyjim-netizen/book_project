# 북적북적 백엔드

도서 쇼핑몰의 FastAPI 백엔드입니다. 회원 인증, 도서 조회, 장바구니, 주문·배송, 리뷰, 쿠폰, 고객지원 기능을 제공합니다. 관리자 API와 도서 추천·판매 분석 API도 포함합니다. SQLAlchemy로 PostgreSQL에 연결합니다.

## 로컬 실행

이 안내는 Windows 명령 프롬프트와 Python 3.12를 기준으로 작성했습니다. PostgreSQL이 실행 중이어야 하며, 아래 DB 초기화 명령을 사용하려면 `psql`이 필요합니다.

### 1. 가상환경 활성화와 패키지 설치

프로젝트 루트에서 실행합니다. 기존 `dl` 가상환경이 있다면 생성 명령은 건너뛰세요.

```cmd
cd /d C:\jh\miniproject02
python -m venv dl
dl\Scripts\activate.bat
cd backend
python -m pip install -r requirements.txt
```

### 2. 환경 변수 설정

`backend` 폴더에 `.env`가 없다면 예제 파일을 복사합니다. 기존 파일이 있다면 아래 복사 명령을 건너뛰고 필요한 값을 확인하세요.

```cmd
copy .env.example .env
```

| 설정 | 용도 |
| --- | --- |
| `DB_HOST`, `DB_PORT` | PostgreSQL 주소와 포트 |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD` | 접속할 데이터베이스 이름과 사용자 정보 |
| `SECRET_KEY` | 인증 토큰에 사용하는 비밀 키 |
| `CORS_ORIGINS` | 브라우저에서 직접 API를 호출할 수 있는 프런트엔드 주소 목록 |
| `PG_MOCK_MODE` | 로컬에서 모의 결제를 사용하려면 `true`로 설정 |

실제 비밀번호와 비밀 키는 `.env`에 저장하고 Git에 올리지 않습니다.

`CORS_ORIGINS`는 JSON 배열로 입력합니다. 복사한 예제의 주소에 따옴표가 빠져 있다면 아래처럼 각 주소를 큰따옴표로 감쌉니다.

```dotenv
CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]
```

### 3. 개발용 데이터베이스 준비

새 개발 DB를 만들 때만 실행합니다. 아래 명령은 `DB_NAME=book`, `DB_USER=postgres`인 예시입니다. 주소·포트·사용자·DB 이름을 변경했다면 명령도 해당 설정에 맞춥니다. 스키마 초기화에 사용하는 DB 계정은 SQL 파일에서 사용하는 PostgreSQL 확장과 스키마를 생성할 수 있어야 합니다.

```cmd
createdb -h localhost -p 5432 -U postgres book
psql -h localhost -p 5432 -U postgres -d book -v ON_ERROR_STOP=1 -f database/schema.sql
```

기본 데이터를 넣으려면 스키마 초기화가 성공한 뒤 실행합니다.

```cmd
psql -h localhost -p 5432 -U postgres -d book -v ON_ERROR_STOP=1 -f database/seed_master.sql
```

### 4. API 서버 시작

`.env`를 읽을 수 있도록 `backend` 폴더에서 실행합니다.

```cmd
python -m uvicorn team_backend.app.main:app --reload
```

터미널에 `Application startup complete`가 표시되면 아래 주소를 열 수 있습니다.

| 주소 | 용도 |
| --- | --- |
| [Swagger UI](http://127.0.0.1:8000/docs) | 등록된 API를 확인하고 브라우저에서 요청을 보내는 화면 |
| [ReDoc](http://127.0.0.1:8000/redoc) | API 명세를 읽는 화면 |
| [헬스 체크](http://127.0.0.1:8000/health) | API 서버와 DB 연결 상태 확인 |

기능 API의 기본 공통 경로는 `/api/v1`입니다. 헬스 체크 응답에서 `database`가 `connected`이면 DB 연결이 확인된 상태입니다. `disconnected`이면 PostgreSQL 실행 상태와 `.env`의 접속 정보를 확인하세요.

## 폴더 구조

| 경로 | 역할 |
| --- | --- |
| `app/main.py` | FastAPI 앱을 만들고 예외 처리, 미들웨어, 라우터를 등록 |
| `app/core/` | 앱 설정, DB 연결, 인증, 예외 처리, 로깅 |
| `app/routers/` | HTTP 요청 경로와 응답 정의 |
| `app/schemas/` | Pydantic 요청·응답 형식 |
| `app/services/` | 주문, 결제, 도서, 고객지원 등의 업무 로직 |
| `app/models/` | SQLAlchemy 테이블 모델 |
| `app/ai/` | 추천, 감성 분석, 판매·고객 분석 |
| `database/` | 신규 DB 스키마와 기본 데이터 SQL |
| `migrations/` | 기존 DB용 변경 SQL |
| `tests/` | 테스트 코드 |

## 자주 보는 오류

| 메시지 | 확인할 곳 |
| --- | --- |
| `No matching distribution found for email-validatorr` | `requirements.txt`의 패키지 이름이 `email-validator`인지 확인합니다. |
| `cannot import name 'register_exception_handlers'` | `app/core/exceptions.py`에 해당 함수가 정의돼 있는지 확인합니다. 로깅 설정은 `app/core/logging_config.py`에 있습니다. |
| `Table 'shop.coupons' is already defined` | `Coupon`, `MemberCoupon`, `Banner`의 모델 정의가 `app/models/promotion.py`에만 있는지 확인합니다. |

터미널에서 원인이 더 필요하면 기본 경로인 `logs/app.log`와 `logs/error.log`도 확인하세요.

## REST API 설계와 현재 구현

아래 표는 [FastAPI 라우터 등록 코드](app/routers/__init__.py)와 [앱 설정](app/main.py)을 기준으로 작성했습니다. 기능 API의 기본 접두사는 `/api/v1`입니다. 요청 필드의 전체 목록과 제약은 실행 중인 서버의 [Swagger UI](http://127.0.0.1:8000/docs)에서도 확인할 수 있습니다.

### 기존 설계의 경로와 현재 경로

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

### 메서드, 입력값, 응답 규칙

- **HTTP 메서드**는 현재 `GET`, `POST`, `PUT`, `DELETE`가 등록돼 있습니다. 장바구니 수량과 선택 상태는 `PUT` 요청에서 전달된 항목만 바꿀 수 있습니다.
- **경로 매개변수**인 `book_id`, `cart_item_id`, `order_id`는 정수입니다. 상품 번호를 전달하던 자리는 현재 도서 번호인 `book_id`를 사용합니다.
- **페이지네이션**은 `page`, `size`로 받고 SQLAlchemy에서 `offset((page - 1) * size).limit(size)` 방식으로 조회합니다. 도서 목록은 기본 `page=1`, `size=20`이며 `size`의 범위는 1~100입니다. 도서 리뷰 목록은 기본 `size=10`입니다. `PageResponse[T]`는 `success`, `items`, `meta`를 반환하며 `meta`에는 `page`, `size`, `total`, `total_pages`가 있습니다.
- **정렬과 검색**에서 도서 목록은 `sort_by`·`direction` 대신 `sort` 하나를 사용합니다. 선택값은 `recent`(기본), `sales`, `price_asc`, `price_desc`, `rating`, `review`, `title`입니다. `keyword`로 도서를 검색하고 `category_id`, `publisher_id`, `author_id`, 가격 범위, 국내 도서 여부, 재고 여부로 결과를 좁힐 수 있습니다.
- **요청 본문**의 필드 이름은 `snake_case`입니다. 회원가입 필수 항목은 `email`, `password`, `password_confirm`, `name`입니다. 도서 등록은 `isbn13`, `title`, `category_id`, `publisher_id`, `list_price`, `sale_price` 등을 사용합니다. 장바구니 추가는 `book_id`, `quantity`를 받습니다. 주문 생성은 주문자 정보와 `receiver`, `receiver_phone`, `zipcode`, `address1` 등 배송지 정보를 받고, `items`를 생략하면 장바구니에서 선택한 항목을 사용합니다. `payment_method`로 결제 수단을 선택하고 실제 결제 요청은 주문 생성 후 `POST /orders/{order_id}/pay`로 진행합니다.
- **인증**은 회원 API에서 FastAPI 의존성으로 확인합니다. HTTP 요청의 `Authorization: Bearer <access_token>` 또는 `access_token` 쿠키를 사용할 수 있습니다. 관리자 API는 `require_admin`, 일부 작업은 `require_superadmin`을 사용합니다. 비회원도 장바구니와 주문 생성에 접근할 수 있으며, 비회원 주문 조회에는 주문번호와 이메일이 필요합니다.

[공통 응답 모델](app/schemas/common.py) · [도서 쿼리](app/routers/books.py) · [도서 조회 로직](app/services/book_service.py) · [회원 요청 모델](app/schemas/member.py) · [도서 요청 모델](app/schemas/book.py) · [장바구니·주문 요청 모델](app/schemas/order.py) · [인증 코드](app/core/security.py)

### HTTP 상태와 오류 코드

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

### AI 모델 연동

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

### 기존 설계에 없던 등록 API

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

### WebSocket 및 별도 경로

- 실시간 상담은 `/api/v1/chat/ws/{room_id}`에 WebSocket으로 연결합니다. HTTP 방식의 채팅 메시지 조회·전송은 위 채팅 표를 참고하세요.
- 서버 상태 확인은 위 표의 `GET /api/v1/health`와 별도 경로인 `GET /health`를 모두 사용할 수 있습니다.
- `app/routers/payments_router.py`의 `/api/payments` 라우터는 현재 앱에 등록되어 있지 않습니다. 등록된 결제 API는 위 주문 표의 경로를 사용합니다.
- 검색·도서 상세·공지·FAQ·관리 화면 등 서버 렌더링 페이지는 [페이지 라우터](app/routers/pages.py)에서 제공합니다.

## 북스토어 메뉴 구조도

이 구조도는 [Vue 라우터](../bookbook2/bookbook2/vue/src/router/index.js)와 각 화면의 소스를 기준으로 작성했습니다. 괄호 안의 주소는 Vue 화면 경로입니다. **[추가]**는 Vue 화면 또는 메뉴 연결이 필요한 항목이고, **[연동 필요]**는 현재 화면에서 쓰는 방식과 이 README의 FastAPI 구현을 연결해야 하는 항목입니다.

```text
📁 북적북적 북스토어
├── 1. 홈 (Home · /)
│   ├── 추천 도서 슬라이드 (선정 도서를 찜한 분야에 따라 우선 표시)
│   ├── 주간 베스트셀러
│   ├── 신간 도서
│   └── 테마별 큐레이션
│
├── 2. 도서 탐색 (Search & Catalog · /books)
│   ├── 전체 도서·카테고리별 목록
│   ├── 통합 검색 결과 (제목·작가·출판사·분야·책 소개)
│   ├── 베스트셀러·신간 보기 및 가격·제목 정렬
│   └── 도서 상세 (/books/:id)
│       ├── 표지·가격·재고와 장바구니 담기·찜
│       ├── 책 소개 및 목차
│       ├── 독자 리뷰·평점·리뷰 작성
│       ├── 리뷰 표현 요약 (현재 긍정·부정 표현 빈도 집계)
│       └── 같은 분야의 도서
│
├── 3. 장바구니 및 주문·결제 (Cart & Order)
│   ├── 장바구니 (/cart)
│   │   └── 수량 변경·선택 삭제·결제 예정 금액 확인
│   ├── 주문서 (/checkout)
│   │   └── 회원·비회원 주문 및 배송지·주문 상품 확인
│   ├── 회원 주문 상세·배송 상태·테스트 결제 영수증 (/orders/:id)
│   ├── 비회원 주문 조회·상세 (/guest-orders, /guest-orders/:id)
│   └── [연동 필요] 결제 승인 결과 표시 및 실패 후 재시도
│
├── 4. 마이페이지 (My Page · /my, 회원 전용)
│   ├── 내 정보 조회·수정 (/profile)
│   ├── 주문 내역 (?tab=orders)
│   ├── 찜한 도서 (?tab=wishes)
│   ├── 취향에 맞는 책 (?tab=picks, 찜과 주문의 관심 분야 기반)
│   └── [추가] 배송지 관리·포인트 내역·쿠폰함·내 리뷰
│
├── 5. 인증 (Authentication)
│   ├── 로그인 (/login, 일반 회원·관리자 공통)
│   ├── 회원가입 (/register)
│   ├── 로그아웃 (상단 메뉴)
│   └── [추가] 비밀번호 재설정 요청
│
├── 6. 고객지원 (Customer Support)
│   ├── [추가] 공지사항 목록·상세
│   ├── [추가] 자주 묻는 질문 (FAQ)
│   ├── [추가] 1:1 문의 (문의 등록·내 문의·답변 확인)
│   └── [추가] 실시간 상담 채팅 (회원 전용)
│
└── 7. 관리자 (Admin · /admin, 관리자 권한 전용)
    ├── 운영 대시보드 (매출·회원 현황·최근 7일 주문)
    ├── 구매 분석 (연령대별·지역별 주문 집계)
    ├── 최근 주문·배송 상태 관리
    ├── 도서 상품 관리 (목록·등록·수정·삭제)
    ├── 회원 관리 (목록 /admin/members, 상세 /admin/members/:id)
    ├── [추가] 재고 부족·재고 변경 이력, 송장 발급, 취소·환불
    ├── [추가] 공지·FAQ·문의 답변·상담 채팅·리뷰 관리
    └── [추가] 판매 예측·고객 분석·AI 모델 실행 이력
```

### 수정 이유와 연결할 API

| 메뉴 | 수정 내용 및 구현에 참고할 경로 |
| --- | --- |
| 홈과 고객지원 | 1:1 문의를 고객지원에 배치하고, 홈에서 바로가기 링크를 제공할 수 있습니다. 답변을 남기는 문의 게시판(`/api/v1/qna`)과 실시간 채팅(`/api/v1/chat/rooms`)은 별도 메뉴로 둡니다. 공지와 FAQ는 `/api/v1/notices`, `/api/v1/faqs`를 연결할 수 있습니다. |
| 추천과 리뷰 | 홈은 선정 도서에 찜한 분야를 반영하고, 마이페이지는 찜과 주문에서 관심 분야를 계산합니다. 도서 상세의 리뷰 요약은 브라우저에서 표현 빈도를 집계합니다. FastAPI 분석 결과를 표시하려면 `GET /api/v1/ai/recommendations`, `GET /api/v1/books/{book_id}/review-stats` 등의 응답을 화면에 연결합니다. |
| 주문과 결제 | 현재 영수증은 테스트 결제를 표시합니다. 비회원 주문 조회는 회원 주문 내역과 별도 메뉴로 유지합니다. Vue가 사용하는 이메일 조회 링크 방식과 이 백엔드의 주문번호·이메일 조회(`GET /api/v1/orders/lookup`)는 요청 방식이 달라, 통합 시 사용할 흐름을 먼저 결정해야 합니다. |
| 마이페이지와 인증 | 배송지·포인트·쿠폰·리뷰는 `/api/v1/members/me/` 아래의 API를 사용할 수 있습니다. 비밀번호 재설정 요청은 `POST /api/v1/auth/password/reset`의 처리 방식과 응답을 확인한 뒤 화면을 연결합니다. |
| 관리자 | 기본 화면에는 주문·배송 관리가 이미 있습니다. 추가 메뉴 후보는 재고 변경 이력, 송장·환불, 고객지원 운영, AI 분석입니다. 해당 경로와 권한은 위 관리자·AI API 표에서 확인할 수 있습니다. |

현재 Vue는 [서점 프로젝트의 별도 FastAPI 앱](../bookbook2/bookbook2/README.md)에서 `/shop/...` API를 사용합니다. 이 문서에서 앞서 정리한 `/api/v1/...` 서버에 연결할 때는 경로와 요청·응답 형식을 함께 맞춰야 합니다. 고객지원 등의 **[추가]** 표시는 Vue 화면 기준입니다.

