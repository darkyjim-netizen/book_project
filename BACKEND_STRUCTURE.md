# 북적북적 백엔드 구조 및 REST API 설계서

## 1. 설계 범위

북적북적의 백엔드는 Python과 FastAPI로 구성한다. SQLAlchemy는 PostgreSQL 연결과 데이터 조회·저장을 맡고, Pydantic은 요청과 응답의 형식을 정의한다. 아래 구조도에는 현재 소스의 파일명을 사용했다. 같은 이름의 파일이 생기지 않도록 `user_model.py`와 `user_crud.py`처럼 파일명에 역할을 표시했다.

## 2. 백엔드 파일 구조

```text
backend/
├── app/
│   ├── __init__.py                  # app 패키지
│   ├── main.py                      # FastAPI 진입점, CORS·라우터·오류 처리 등록
│   ├── database.py                  # PostgreSQL 연결과 요청별 DB 세션 관리
│   ├── core/
│   │   ├── config.py                # CORS 허용 출처 등 환경 설정
│   │   ├── security.py              # 비밀번호 해시와 검증
│   │   └── api_errors.py            # HTTP 오류 응답과 입력 검증 오류 처리
│   ├── models/
│   │   ├── user_model.py            # 회원 정보와 권한
│   │   ├── product_model.py         # 도서 상품과 리뷰
│   │   ├── category_model.py        # 도서 분류
│   │   ├── order_model.py           # 주문 항목, 배송지, 금액, 결제 상태
│   │   └── cart_model.py            # 회원별 장바구니 상품과 수량
│   ├── auth/
│   │   ├── auth_router.py           # 회원가입·로그인·갱신·내 정보 API
│   │   ├── auth_schemas.py          # 인증 요청·토큰·회원 응답 형식
│   │   ├── auth_service.py          # 가입 중복 검사, 로그인과 갱신 처리
│   │   ├── auth_dependencies.py     # Bearer JWT와 회원·관리자 권한 확인
│   │   ├── jwt_tokens.py            # JWT 발급, 서명·만료·토큰 종류 검증
│   │   ├── session_router.py        # 기존 화면용 세션 로그인 API
│   │   └── session_dependencies.py  # 기존 세션의 회원·관리자 권한 확인
│   ├── routers/
│   │   ├── products_router.py       # 상품 목록·상세 조회, 관리자 상품 CRUD
│   │   ├── cart_router.py           # 장바구니 조회·추가·수량 수정·삭제
│   │   ├── orders_router.py         # 주문 생성·목록·상세 조회
│   │   ├── ai_router.py             # 추천 도서와 리뷰 감정 요약
│   │   ├── admin_dashboard_router.py # 관리자 요약 통계와 구매 분석
│   │   ├── profile_router.py        # 기존 화면용 내 정보 조회·수정·탈퇴
│   │   ├── admin_members_router.py  # 기존 화면용 관리자 회원 관리
│   │   ├── product_schemas.py       # 상품 등록·수정 입력과 상품 응답
│   │   ├── order_schemas.py         # 주문·결제 입력과 주문 응답
│   │   ├── member_schemas.py        # 기존 회원·관리자 API 데이터 형식
│   │   └── page_schema.py           # 공통 페이지 응답 PageResponse[T]
│   └── crud/
│       ├── user_crud.py             # 회원 조회와 등록
│       ├── product_crud.py          # 도서 검색·정렬·페이지네이션
│       └── order_crud.py            # 주문 저장과 재고·장바구니 반영
├── tests/                           # [예정] 인증·상품·주문 Pytest 테스트
├── alembic/                         # [예정] DB 변경 이력 관리
│   └── versions/                    # [예정] 변경 버전별 마이그레이션
├── .env                             # 로컬 환경 변수
├── .env.example                     # [예정] 환경 변수 예시
├── requirements.txt                 # Python 의존성
├── alembic.ini                      # [예정] Alembic 설정
└── BACKEND_STRUCTURE.md             # 백엔드 구조와 REST API 설계서
```

### 요청이 처리되는 흐름

1. `main.py`에 등록한 라우터가 요청을 받는다. 본문과 경로·쿼리 값은 요청 모델과 타입으로 검증한다.
2. 회원 전용 API는 `Depends`에서 Bearer JWT를 검사한다. 관리자 전용 API는 DB에서 현재 회원의 역할도 확인한다.
3. 라우터가 서비스 또는 CRUD 함수에 처리를 위임한다. SQLAlchemy 모델과 DB 세션을 사용해 조회·저장한다.
4. Pydantic 응답 모델에 맞춰 결과를 반환한다. 주문은 서버가 단가와 재고를 확인하고, 주문 저장·재고 차감·장바구니 반영을 한 트랜잭션에서 처리한다.

## 3. REST API 엔드포인트

`GET`은 조회, `POST`는 생성·인증, `PUT`은 전체 수정, `PATCH`는 일부 수정, `DELETE`는 삭제를 의미한다.

| 메서드 | 경로 | 접근 권한 | 처리 및 성공 응답 |
| --- | --- | --- | --- |
| POST | `/api/auth/signup` | 공개 | 회원가입 · 201 `MemberMeResponse` |
| POST | `/api/auth/login` | 공개 | 이메일 로그인 · 200 `TokenResponse` |
| POST | `/api/auth/refresh` | 유효한 refresh 토큰 | 토큰 재발급 · 200 `TokenResponse` |
| GET | `/api/auth/me` | 회원 | 로그인 회원 정보 · 200 `MemberMeResponse` |
| GET | `/api/products` | 공개 | 검색·필터·정렬된 목록 · 200 `PageResponse[ProductResponse]` |
| GET | `/api/products/{product_id}` | 공개 | 상품 상세 · 200 `ProductResponse` |
| POST | `/api/products` | 관리자 | 상품 등록 · 201 `ProductResponse` |
| PUT | `/api/products/{product_id}` | 관리자 | 상품 전체 수정 · 200 `ProductResponse` |
| DELETE | `/api/products/{product_id}` | 관리자 | 상품 비활성화 · 200 |
| GET | `/api/cart` | 회원 | 내 장바구니 · 200 `CartItemResponse[]` |
| POST | `/api/cart` | 회원 | 새 항목 추가는 201, 기존 항목 수량 증가 시 200 · `CartItemResponse` |
| PATCH | `/api/cart/{cart_item_id}` | 소유 회원 | 항목 수량 변경 · 200 `CartItemResponse` |
| DELETE | `/api/cart/{cart_item_id}` | 소유 회원 | 항목 삭제 · 200 |
| GET | `/api/orders` | 회원 | 내 주문 목록 · 200 `PageResponse[OrderResponse]` |
| POST | `/api/orders` | 회원 | 주문 생성 · 201 `OrderResponse` |
| GET | `/api/orders/{order_id}` | 소유 회원 | 주문 상세 · 200 `OrderResponse` |
| GET | `/api/ai/recommendations` | 공개 | 추천 도서 · 200 `AIRecommendationResponse` |
| GET | `/api/ai/reviews/{product_id}/sentiment` | 공개 | 리뷰 감정 요약 · 200 `SentimentResponse` |
| GET | `/api/admin/dashboard/stats` | 관리자 | 매출·회원·주문 요약 · 200 `AdminStatsResponse` |
| GET | `/api/admin/dashboard/analytics` | 관리자 | 지역·연령대·카테고리 분석 · 200 `AdminAnalyticsResponse` |

회원 API는 `Authorization: Bearer <access_token>`을 사용한다. `/auth`, `/members`, `/admin/members`는 기존 화면과 연결되는 세션 인증 경로다.

## 4. 경로 및 쿼리 매개변수

경로 변수 `product_id`, `cart_item_id`, `order_id`는 각각 상품·장바구니 항목·주문의 정수 식별자다.

| 쿼리 변수 | 타입 | 기본값 | 적용 범위 |
| --- | --- | --- | --- |
| `page` | 정수 | 1 | 상품 및 주문 목록 |
| `size` | 정수 | 10 | 상품 및 주문 목록. 1~100개 |
| `sort_by` | 문자열 | `created_at` | 상품 목록. `created_at` 또는 `price` |
| `direction` | 문자열 | `desc` | 상품 목록. `asc` 또는 `desc` |
| `keyword` | 문자열 | 생략 가능 | 상품 제목·작가의 부분 일치 |
| `category_id` | 정수 | 생략 가능 | 상품 목록의 카테고리 일치 |

상품 목록은 검색어와 카테고리를 함께 적용할 수 있다. 필터링된 건수로 `total`을 계산한 뒤, 허용된 열을 기준으로 `.order_by()`를 적용한다. 페이지 범위는 `.offset((page - 1) * size).limit(size)`로 가져온다. 추천 API도 `size`와 `category_id`를 지원하며 최대 50개까지 요청할 수 있다.

## 5. 요청 및 응답 모델

요청 예시는 스네이크 케이스로 작성했다. 명세의 `Email`, `ProductId`, `ReceiverName` 같은 이름도 해당 입력에서 허용한다. 응답 키에는 스네이크 케이스를 사용한다.

| 요청 | 주요 본문 |
| --- | --- |
| 회원가입 | `email`, `password`, `name` |
| 로그인 | `email`, `password` |
| 토큰 갱신 | `refresh_token` |
| 상품 등록·전체 수정 | `title`, `author`, `price`, `stock`, `category_id` |
| 장바구니 추가 | `product_id`, `quantity` |
| 장바구니 수량 변경 | `quantity` |
| 주문 생성 | `receiver_name`, `address`, `payment_info`, `items`. `region`, `age_group`은 선택 |

```json
{
  "receiver_name": "홍길동",
  "address": "서울시 예시로 1",
  "payment_info": { "method": "test" },
  "items": [{ "product_id": 1, "quantity": 2 }]
}
```

| 응답 모델 | 주요 필드 |
| --- | --- |
| `ProductResponse` | `id`, `title`, `author`, `price`, `stock`, `category_id`, `created_at` |
| `PageResponse[T]` | `items`, `total`, `page`, `size` |
| `TokenResponse` | `access_token`, `refresh_token`, `token_type` |
| `MemberMeResponse` | `id`, `email`, `name`, `role`, `is_active`, `created_at` |
| `CartItemResponse` | `id`, `product_id`, `quantity` |
| `OrderResponse` | `id`, `receiver_name`, `address`, `items`, `total`, `payment_status`, `created_at` |
| `AIRecommendationResponse` | `items`, `strategy` |
| `SentimentResponse` | `product_id`, `review_count`, 긍정·부정 비율과 키워드별 집계 |
| `AdminStatsResponse` | `total_sales`, `member_count`, `order_count`, `daily_orders` |
| `AdminAnalyticsResponse` | `orders_by_region`, `orders_by_age_group`, `units_by_category` |

## 6. 상태 코드 및 오류 응답

| 상태 | 발생 조건 | 오류 코드 |
| --- | --- | --- |
| 200 OK | 조회·수정·삭제 및 인증 처리 성공 | |
| 201 Created | 회원·상품·장바구니 항목·주문 생성 성공 | |
| 400 Bad Request | 입력 검증 실패, 중복 이메일, 재고 부족 | `INVALID_INPUT_VALUE`, `DUPLICATE_EMAIL`, `OUT_OF_STOCK` |
| 401 Unauthorized | 토큰 누락·만료·검증 실패, 로그인 정보 불일치 또는 토큰의 회원 없음 | `UNAUTHORIZED_ACCESS`, `MEMBER_NOT_FOUND` |
| 403 Forbidden | 회원에게 관리자 권한이 없음 | `ADMIN_PERMISSION_REQUIRED` |
| 404 Not Found | 상품, 내 장바구니 항목 또는 내 주문을 찾을 수 없음 | `PRODUCT_NOT_FOUND`, `CART_ITEM_NOT_FOUND`, `ORDER_NOT_FOUND` |
| 500 Internal Server Error | 처리되지 않은 서버 내부 오류 | |

도메인 오류는 `code`와 `message`를 반환한다. 입력 검증 오류는 문제가 발생한 필드를 `fields`에 함께 제공한다.

## 7. 아직 구현하지 못한 항목과 다음 작업

### 남은 API와 백엔드 구조 한눈에 보기

3절에 정리한 확정 REST API는 메서드 기준 20개 모두 라우터가 연결되어 있다. 아래의 신규 API 경로와 파일명은 후속 작업에서 사용할 제안이다.

| 작업 | 남은 API 또는 처리 | 백엔드 구조 항목 |
| --- | --- | --- |
| 카테고리 | 카테고리 초기 데이터를 준비하거나 관리자 등록 API `POST /api/categories`를 추가한다. 프런트엔드 필터에 필요하면 공개 목록 `GET /api/categories`도 추가한다. | 기존 `app/models/category_model.py` 활용. API를 추가할 경우 `app/routers/categories_router.py` 추가 |
| 리뷰 등록 | 회원이 도서 리뷰를 저장하는 `POST /api/products/{product_id}/reviews`를 추가한다. | 기존 `app/models/product_model.py`의 `Review` 활용. `app/routers/reviews_router.py` 추가 |
| 개인화 추천 | 기존 `GET /api/ai/recommendations`에 회원의 찜·구매 이력 기반 추천을 추가한다. | `app/routers/ai_router.py` 확장. 찜 데이터의 저장·조회 범위 확정 |
| 감정 분석 고도화 | 기존 `GET /api/ai/reviews/{product_id}/sentiment`의 키워드 규칙을 모델 기반 분석으로 확장하는 경우 분석 기준을 정한다. | `app/routers/ai_router.py`의 분석 로직 확장 |
| 실제 결제 | 결제사를 연동하는 경우 승인·실패·취소·환불을 처리한다. 별도 API 경로는 결제사 연동 방식에 맞춰 확정한다. | `app/crud/order_crud.py`의 주문 처리와 결제 결과 저장 구조 확장 |
| 자동화 테스트 | 기존 API의 입력 검증, 권한, 조회 및 주문 흐름을 검증한다. | `tests/test_auth.py`, `tests/test_products.py`, `tests/test_orders.py` |
| DB 마이그레이션 | 테이블·컬럼 변경 이력을 관리한다. | `alembic.ini`, `alembic/versions/` |
| 환경 변수 예시 | DB·세션·JWT·CORS 설정 방법을 공유한다. | `.env.example` |
| 통합 검증 | 실제 PostgreSQL과 프런트엔드에서 기존 API를 호출해 인증·주문 흐름을 확인한다. | DB 연결 설정 및 프런트엔드 API 호출부 |

### 아직 없는 기능과 프로젝트 설정

- [ ] **카테고리 초기 데이터 또는 관리 API** · 상품 등록에 필요한 카테고리를 추가하는 방법을 마련한다. 현재는 DB에 이미 등록된 카테고리만 상품에 지정할 수 있다.
- [ ] **리뷰 등록 API** · 리뷰를 저장하는 API를 추가한다. 현재 리뷰 감정 요약 API는 DB에 저장된 리뷰를 읽어서 집계한다.
- [ ] **Alembic 마이그레이션** · `alembic.ini`와 `alembic/versions/`를 추가하고 첫 마이그레이션을 작성한다. 현재 앱은 시작할 때 없는 테이블을 생성한다.
- [ ] **환경 변수 예시** · `.env.example`에 DB 연결, 세션 키, JWT 키, CORS 설정에 필요한 변수명과 예시 값을 정리한다.
- [ ] **Pytest 자동화 테스트** · 인증과 관리자 권한, 상품 검색과 페이지네이션, 장바구니와 주문의 소유권 및 재고 차감을 검증하는 테스트를 추가한다.

### 기본 구현을 확장할 항목

- [ ] **개인화 추천** · 현재 최신 상품 기준 추천에 회원의 찜·구매 이력을 활용하는 개인화 규칙이나 모델을 추가한다.
- [ ] **리뷰 감정 분석 고도화** · 현재 긍정·부정 키워드 빈도를 집계한다. 모델 기반 분석을 적용할 경우 한국어 리뷰로 결과를 비교하고 비율 계산 기준을 정한다.
- [ ] **실제 결제 연동** · 현재 주문은 테스트 결제로 처리된다. 실제 결제가 필요하면 승인 확인, 실패·취소·환불 처리를 구현하고 관리자 매출에서 테스트 주문과 실제 거래를 구분한다.

### 구현 후 확인할 항목

- [ ] **PostgreSQL과 프런트엔드 연동 검증** · PostgreSQL에서 가입부터 장바구니·주문까지 실제 HTTP 요청으로 실행하고, 프런트엔드에서 Bearer 토큰 전달과 갱신, 오류 응답 표시를 확인한다.

## 8. 실행 및 API 확인

Windows CMD에서 `C:\jh\miniproject02\backend`로 이동해 실행한다.

```cmd
..\dl\Scripts\python.exe -m uvicorn app.main:app --reload
```

의존성 설치가 필요하면 같은 가상환경에서 `..\dl\Scripts\python.exe -m pip install -r requirements.txt`를 실행한다. 서버가 시작되면 [Swagger API 문서](http://127.0.0.1:8000/docs)에서 요청과 응답 형식을 확인할 수 있다.

