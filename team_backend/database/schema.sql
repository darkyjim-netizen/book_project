-- =============================================================================
--  BookStore AI Commerce Platform - PostgreSQL 16 Schema
--  Database : business
--  Encoding : UTF8
--  Author   : BookStore Platform Team
--  Version  : 1.0.0
-- =============================================================================
--  실행 방법
--    psql -U postgres -h localhost -p 5432 -d business -f 01_schema.sql
-- =============================================================================

SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SET timezone = 'Asia/Seoul';

-- -----------------------------------------------------------------------------
-- 0. 확장 모듈
-- -----------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "pgcrypto";      -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "pg_trgm";       -- 유사도 기반 도서 검색
CREATE EXTENSION IF NOT EXISTS "btree_gin";     -- 복합 GIN 인덱스

-- -----------------------------------------------------------------------------
-- 0-1. 스키마
-- -----------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS shop;
CREATE SCHEMA IF NOT EXISTS ai;
CREATE SCHEMA IF NOT EXISTS log;

SET search_path TO shop, public;

-- -----------------------------------------------------------------------------
-- 0-2. 공통 ENUM 타입
-- -----------------------------------------------------------------------------
CREATE TYPE member_role      AS ENUM ('USER', 'SELLER', 'STAFF', 'ADMIN');
CREATE TYPE member_status    AS ENUM ('ACTIVE', 'DORMANT', 'SUSPENDED', 'WITHDRAWN');
CREATE TYPE gender_type      AS ENUM ('M', 'F', 'N');
CREATE TYPE book_status      AS ENUM ('SALE', 'SOLDOUT', 'STOP', 'PREORDER', 'DELETED');
CREATE TYPE order_status     AS ENUM ('PENDING', 'PAID', 'PREPARING', 'SHIPPING',
                                      'DELIVERED', 'CONFIRMED', 'CANCELLED',
                                      'RETURN_REQ', 'RETURNED', 'EXCHANGE_REQ', 'EXCHANGED');
CREATE TYPE payment_method   AS ENUM ('CARD', 'VBANK', 'TRANSFER', 'PHONE',
                                      'KAKAOPAY', 'NAVERPAY', 'TOSSPAY', 'POINT');
CREATE TYPE payment_status   AS ENUM ('READY', 'PAID', 'CANCELLED', 'PARTIAL_CANCELLED', 'FAILED');
CREATE TYPE shipment_status  AS ENUM ('READY', 'PICKED', 'IN_TRANSIT', 'OUT_FOR_DELIVERY',
                                      'DELIVERED', 'FAILED', 'RETURNING');
CREATE TYPE sentiment_label  AS ENUM ('POSITIVE', 'NEUTRAL', 'NEGATIVE');
CREATE TYPE qna_status       AS ENUM ('WAITING', 'ANSWERED', 'CLOSED');
CREATE TYPE chat_room_status AS ENUM ('OPEN', 'ASSIGNED', 'CLOSED');
CREATE TYPE coupon_type      AS ENUM ('AMOUNT', 'PERCENT', 'FREESHIP');
CREATE TYPE point_reason     AS ENUM ('ORDER_SAVE', 'ORDER_USE', 'REVIEW', 'EVENT',
                                      'ADMIN_ADJUST', 'EXPIRE', 'CANCEL_RESTORE');

-- =============================================================================
-- 1. 회원 도메인
-- =============================================================================

-- 1-1. 회원 등급
CREATE TABLE shop.member_grades (
    grade_id        SMALLSERIAL PRIMARY KEY,
    grade_code      VARCHAR(20)  NOT NULL UNIQUE,
    grade_name      VARCHAR(50)  NOT NULL,
    min_amount      NUMERIC(12,0) NOT NULL DEFAULT 0,
    discount_rate   NUMERIC(5,2)  NOT NULL DEFAULT 0,
    point_rate      NUMERIC(5,2)  NOT NULL DEFAULT 1.0,
    free_ship_limit NUMERIC(12,0) NOT NULL DEFAULT 20000,
    sort_order      SMALLINT     NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);
COMMENT ON TABLE  shop.member_grades IS '회원 등급 정책';
COMMENT ON COLUMN shop.member_grades.min_amount IS '등급 달성을 위한 최근 6개월 누적 구매금액';

-- 1-2. 회원
CREATE TABLE shop.members (
    member_id       BIGSERIAL PRIMARY KEY,
    uuid            UUID         NOT NULL DEFAULT gen_random_uuid(),
    email           VARCHAR(190) NOT NULL UNIQUE,
    password_hash   VARCHAR(255),
    name            VARCHAR(60)  NOT NULL,
    nickname        VARCHAR(60),
    phone           VARCHAR(20),
    birth_date      DATE,
    gender          gender_type  NOT NULL DEFAULT 'N',
    role            member_role  NOT NULL DEFAULT 'USER',
    status          member_status NOT NULL DEFAULT 'ACTIVE',
    grade_id        SMALLINT     NOT NULL DEFAULT 1 REFERENCES shop.member_grades(grade_id),
    point_balance   INTEGER      NOT NULL DEFAULT 0 CHECK (point_balance >= 0),
    total_paid      NUMERIC(14,0) NOT NULL DEFAULT 0,
    order_count     INTEGER      NOT NULL DEFAULT 0,
    marketing_agree BOOLEAN      NOT NULL DEFAULT false,
    sms_agree       BOOLEAN      NOT NULL DEFAULT false,
    email_agree     BOOLEAN      NOT NULL DEFAULT false,
    oauth_provider  VARCHAR(20),
    oauth_id        VARCHAR(190),
    profile_image   VARCHAR(255),
    last_login_at   TIMESTAMPTZ,
    login_fail_cnt  SMALLINT     NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    withdrawn_at    TIMESTAMPTZ
);
CREATE INDEX idx_members_status     ON shop.members(status);
CREATE INDEX idx_members_grade      ON shop.members(grade_id);
CREATE INDEX idx_members_created    ON shop.members(created_at DESC);
CREATE INDEX idx_members_oauth      ON shop.members(oauth_provider, oauth_id);
CREATE INDEX idx_members_name_trgm  ON shop.members USING gin (name gin_trgm_ops);
COMMENT ON TABLE shop.members IS '회원 마스터. 이탈 예측/구매 분석 AI의 기준 테이블';

-- 1-3. 배송지
CREATE TABLE shop.member_addresses (
    address_id      BIGSERIAL PRIMARY KEY,
    member_id       BIGINT       NOT NULL REFERENCES shop.members(member_id) ON DELETE CASCADE,
    alias           VARCHAR(50)  NOT NULL DEFAULT '기본 배송지',
    receiver        VARCHAR(60)  NOT NULL,
    phone           VARCHAR(20)  NOT NULL,
    zipcode         VARCHAR(10)  NOT NULL,
    address1        VARCHAR(255) NOT NULL,
    address2        VARCHAR(255),
    request_memo    VARCHAR(255),
    is_default      BOOLEAN      NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX idx_addresses_member ON shop.member_addresses(member_id, is_default DESC);

-- 1-4. 회원 탈퇴 이력
CREATE TABLE shop.member_withdrawals (
    withdrawal_id   BIGSERIAL PRIMARY KEY,
    member_id       BIGINT       NOT NULL,
    email_masked    VARCHAR(190) NOT NULL,
    reason_code     VARCHAR(40)  NOT NULL,
    reason_text     TEXT,
    total_paid      NUMERIC(14,0) NOT NULL DEFAULT 0,
    joined_at       TIMESTAMPTZ,
    withdrawn_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- 1-5. 로그인 이력 (이탈 예측 피처)
CREATE TABLE log.login_histories (
    login_id        BIGSERIAL PRIMARY KEY,
    member_id       BIGINT,
    email           VARCHAR(190),
    success         BOOLEAN      NOT NULL,
    ip_address      INET,
    user_agent      VARCHAR(400),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX idx_login_hist_member ON log.login_histories(member_id, created_at DESC);

-- =============================================================================
-- 2. 도서(상품) 도메인
-- =============================================================================

-- 2-1. 카테고리 (계층 구조)
CREATE TABLE shop.categories (
    category_id     INTEGER PRIMARY KEY,
    parent_id       INTEGER REFERENCES shop.categories(category_id),
    name            VARCHAR(80)  NOT NULL,
    full_path       VARCHAR(255) NOT NULL,
    depth           SMALLINT     NOT NULL DEFAULT 1,
    sort_order      SMALLINT     NOT NULL DEFAULT 0,
    is_active       BOOLEAN      NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX idx_categories_parent ON shop.categories(parent_id, sort_order);
COMMENT ON COLUMN shop.categories.full_path IS '예) 국내도서 > 소설 > 한국소설';

-- 2-2. 출판사
CREATE TABLE shop.publishers (
    publisher_id    SERIAL PRIMARY KEY,
    name            VARCHAR(120) NOT NULL UNIQUE,
    country_code    CHAR(2)      NOT NULL DEFAULT 'KR',
    homepage        VARCHAR(255),
    description     TEXT,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- 2-3. 저자
CREATE TABLE shop.authors (
    author_id       SERIAL PRIMARY KEY,
    name            VARCHAR(120) NOT NULL,
    name_original   VARCHAR(160),
    country_code    CHAR(2)      NOT NULL DEFAULT 'KR',
    biography       TEXT,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX idx_authors_name_trgm ON shop.authors USING gin (name gin_trgm_ops);

-- 2-4. 도서
CREATE TABLE shop.books (
    book_id         BIGSERIAL PRIMARY KEY,
    isbn13          VARCHAR(13)  NOT NULL UNIQUE,
    isbn10          VARCHAR(10),
    title           VARCHAR(300) NOT NULL,
    subtitle        VARCHAR(300),
    title_original  VARCHAR(300),
    category_id     INTEGER      NOT NULL REFERENCES shop.categories(category_id),
    publisher_id    INTEGER      NOT NULL REFERENCES shop.publishers(publisher_id),
    translator      VARCHAR(200),
    list_price      NUMERIC(10,0) NOT NULL CHECK (list_price >= 0),
    sale_price      NUMERIC(10,0) NOT NULL CHECK (sale_price >= 0),
    discount_rate   NUMERIC(5,2) NOT NULL DEFAULT 0,
    point_rate      NUMERIC(5,2) NOT NULL DEFAULT 1.0,
    stock_qty       INTEGER      NOT NULL DEFAULT 0 CHECK (stock_qty >= 0),
    safety_stock    INTEGER      NOT NULL DEFAULT 5,
    status          book_status  NOT NULL DEFAULT 'SALE',
    is_domestic     BOOLEAN      NOT NULL DEFAULT true,
    language_code   CHAR(2)      NOT NULL DEFAULT 'ko',
    published_date  DATE,
    page_count      INTEGER,
    weight_g        INTEGER,
    size_mm         VARCHAR(40),
    binding         VARCHAR(40),
    edition         VARCHAR(40),
    summary         TEXT,
    description     TEXT,
    table_of_contents TEXT,
    publisher_review TEXT,
    cover_image     VARCHAR(255),
    is_ebook_available BOOLEAN   NOT NULL DEFAULT false,
    is_gift_wrap    BOOLEAN      NOT NULL DEFAULT true,
    view_count      INTEGER      NOT NULL DEFAULT 0,
    sales_count     INTEGER      NOT NULL DEFAULT 0,
    review_count    INTEGER      NOT NULL DEFAULT 0,
    rating_avg      NUMERIC(3,2) NOT NULL DEFAULT 0,
    sentiment_score NUMERIC(5,4),
    search_vector   TSVECTOR,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX idx_books_category   ON shop.books(category_id, status);
CREATE INDEX idx_books_publisher  ON shop.books(publisher_id);
CREATE INDEX idx_books_status      ON shop.books(status) WHERE status = 'SALE';
CREATE INDEX idx_books_sales       ON shop.books(sales_count DESC);
CREATE INDEX idx_books_published   ON shop.books(published_date DESC);
CREATE INDEX idx_books_title_trgm  ON shop.books USING gin (title gin_trgm_ops);
CREATE INDEX idx_books_search_vec  ON shop.books USING gin (search_vector);
COMMENT ON COLUMN shop.books.sentiment_score IS '리뷰 감성분석 집계 점수 (-1.0 ~ 1.0)';

-- 2-5. 도서-저자 매핑
CREATE TABLE shop.book_authors (
    book_id         BIGINT  NOT NULL REFERENCES shop.books(book_id) ON DELETE CASCADE,
    author_id       INTEGER NOT NULL REFERENCES shop.authors(author_id) ON DELETE CASCADE,
    role            VARCHAR(20) NOT NULL DEFAULT 'AUTHOR',
    sort_order      SMALLINT NOT NULL DEFAULT 0,
    PRIMARY KEY (book_id, author_id, role)
);

-- 2-6. 도서 이미지
CREATE TABLE shop.book_images (
    image_id        BIGSERIAL PRIMARY KEY,
    book_id         BIGINT  NOT NULL REFERENCES shop.books(book_id) ON DELETE CASCADE,
    image_url       VARCHAR(255) NOT NULL,
    image_type      VARCHAR(20)  NOT NULL DEFAULT 'DETAIL',
    sort_order      SMALLINT NOT NULL DEFAULT 0
);

-- 2-7. 재고 변동 이력
CREATE TABLE log.stock_histories (
    history_id      BIGSERIAL PRIMARY KEY,
    book_id         BIGINT  NOT NULL,
    change_qty      INTEGER NOT NULL,
    after_qty       INTEGER NOT NULL,
    reason          VARCHAR(40) NOT NULL,
    ref_id          BIGINT,
    created_by      BIGINT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_stock_hist_book ON log.stock_histories(book_id, created_at DESC);

-- =============================================================================
-- 3. 장바구니 / 위시리스트 / 조회 이력
-- =============================================================================
CREATE TABLE shop.carts (
    cart_id         BIGSERIAL PRIMARY KEY,
    member_id       BIGINT REFERENCES shop.members(member_id) ON DELETE CASCADE,
    session_key     VARCHAR(64),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_carts_member  ON shop.carts(member_id) WHERE member_id IS NOT NULL;
CREATE UNIQUE INDEX uq_carts_session ON shop.carts(session_key) WHERE session_key IS NOT NULL;

CREATE TABLE shop.cart_items (
    cart_item_id    BIGSERIAL PRIMARY KEY,
    cart_id         BIGINT  NOT NULL REFERENCES shop.carts(cart_id) ON DELETE CASCADE,
    book_id         BIGINT  NOT NULL REFERENCES shop.books(book_id) ON DELETE CASCADE,
    quantity        INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
    is_selected     BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (cart_id, book_id)
);

CREATE TABLE shop.wishlists (
    wishlist_id     BIGSERIAL PRIMARY KEY,
    member_id       BIGINT NOT NULL REFERENCES shop.members(member_id) ON DELETE CASCADE,
    book_id         BIGINT NOT NULL REFERENCES shop.books(book_id) ON DELETE CASCADE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (member_id, book_id)
);

CREATE TABLE log.recent_views (
    view_id         BIGSERIAL PRIMARY KEY,
    member_id       BIGINT,
    session_key     VARCHAR(64),
    book_id         BIGINT NOT NULL,
    dwell_seconds   INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_recent_views_member ON log.recent_views(member_id, created_at DESC);
CREATE INDEX idx_recent_views_book   ON log.recent_views(book_id);

CREATE TABLE log.search_logs (
    search_id       BIGSERIAL PRIMARY KEY,
    member_id       BIGINT,
    keyword         VARCHAR(200) NOT NULL,
    result_count    INTEGER NOT NULL DEFAULT 0,
    clicked_book_id BIGINT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_search_logs_keyword ON log.search_logs(keyword);

-- =============================================================================
-- 4. 주문 / 결제 / 배송
-- =============================================================================
CREATE TABLE shop.orders (
    order_id        BIGSERIAL PRIMARY KEY,
    order_no        VARCHAR(30)  NOT NULL UNIQUE,
    member_id       BIGINT REFERENCES shop.members(member_id),
    orderer_name    VARCHAR(60)  NOT NULL,
    orderer_phone   VARCHAR(20)  NOT NULL,
    orderer_email   VARCHAR(190) NOT NULL,
    status          order_status NOT NULL DEFAULT 'PENDING',
    item_amount     NUMERIC(12,0) NOT NULL DEFAULT 0,
    discount_amount NUMERIC(12,0) NOT NULL DEFAULT 0,
    coupon_amount   NUMERIC(12,0) NOT NULL DEFAULT 0,
    point_used      NUMERIC(12,0) NOT NULL DEFAULT 0,
    ship_fee        NUMERIC(10,0) NOT NULL DEFAULT 0,
    total_amount    NUMERIC(12,0) NOT NULL DEFAULT 0,
    point_saved     NUMERIC(10,0) NOT NULL DEFAULT 0,
    receiver        VARCHAR(60)  NOT NULL,
    receiver_phone  VARCHAR(20)  NOT NULL,
    zipcode         VARCHAR(10)  NOT NULL,
    address1        VARCHAR(255) NOT NULL,
    address2        VARCHAR(255),
    request_memo    VARCHAR(255),
    is_gift_wrap    BOOLEAN      NOT NULL DEFAULT false,
    ordered_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    paid_at         TIMESTAMPTZ,
    delivered_at    TIMESTAMPTZ,
    confirmed_at    TIMESTAMPTZ,
    cancelled_at    TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX idx_orders_member   ON shop.orders(member_id, ordered_at DESC);
CREATE INDEX idx_orders_status   ON shop.orders(status, ordered_at DESC);
CREATE INDEX idx_orders_date     ON shop.orders(ordered_at DESC);
CREATE INDEX idx_orders_paid_day ON shop.orders((ordered_at::date)) WHERE status <> 'CANCELLED';

CREATE TABLE shop.order_items (
    order_item_id   BIGSERIAL PRIMARY KEY,
    order_id        BIGINT  NOT NULL REFERENCES shop.orders(order_id) ON DELETE CASCADE,
    book_id         BIGINT  NOT NULL REFERENCES shop.books(book_id),
    book_title      VARCHAR(300) NOT NULL,
    unit_price      NUMERIC(10,0) NOT NULL,
    quantity        INTEGER NOT NULL CHECK (quantity > 0),
    item_discount   NUMERIC(10,0) NOT NULL DEFAULT 0,
    item_total      NUMERIC(12,0) NOT NULL,
    status          order_status NOT NULL DEFAULT 'PENDING',
    is_reviewed     BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_order_items_order ON shop.order_items(order_id);
CREATE INDEX idx_order_items_book  ON shop.order_items(book_id);

CREATE TABLE shop.payments (
    payment_id      BIGSERIAL PRIMARY KEY,
    order_id        BIGINT  NOT NULL REFERENCES shop.orders(order_id) ON DELETE CASCADE,
    pg_provider     VARCHAR(30)  NOT NULL DEFAULT 'INICIS',
    pg_tid          VARCHAR(100),
    method          payment_method NOT NULL,
    status          payment_status NOT NULL DEFAULT 'READY',
    amount          NUMERIC(12,0) NOT NULL,
    cancelled_amount NUMERIC(12,0) NOT NULL DEFAULT 0,
    card_name       VARCHAR(60),
    card_no_masked  VARCHAR(30),
    install_month   SMALLINT NOT NULL DEFAULT 0,
    vbank_bank      VARCHAR(60),
    vbank_no        VARCHAR(40),
    vbank_holder    VARCHAR(60),
    vbank_due       TIMESTAMPTZ,
    receipt_url     VARCHAR(255),
    requested_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    approved_at     TIMESTAMPTZ,
    cancelled_at    TIMESTAMPTZ
);
CREATE INDEX idx_payments_order ON shop.payments(order_id);
CREATE INDEX idx_payments_tid   ON shop.payments(pg_tid);

CREATE TABLE log.payment_logs (
    log_id          BIGSERIAL PRIMARY KEY,
    payment_id      BIGINT,
    order_no        VARCHAR(30),
    action          VARCHAR(40) NOT NULL,
    request_body    JSONB,
    response_body   JSONB,
    result_code     VARCHAR(20),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE shop.refunds (
    refund_id       BIGSERIAL PRIMARY KEY,
    order_id        BIGINT  NOT NULL REFERENCES shop.orders(order_id),
    payment_id      BIGINT REFERENCES shop.payments(payment_id),
    refund_amount   NUMERIC(12,0) NOT NULL,
    point_restore   NUMERIC(10,0) NOT NULL DEFAULT 0,
    reason_code     VARCHAR(40) NOT NULL,
    reason_text     TEXT,
    processed_by    BIGINT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ
);

CREATE TABLE shop.shipments (
    shipment_id     BIGSERIAL PRIMARY KEY,
    order_id        BIGINT  NOT NULL REFERENCES shop.orders(order_id) ON DELETE CASCADE,
    carrier_code    VARCHAR(20)  NOT NULL DEFAULT 'CJ',
    carrier_name    VARCHAR(60)  NOT NULL DEFAULT 'CJ대한통운',
    invoice_no      VARCHAR(40),
    status          shipment_status NOT NULL DEFAULT 'READY',
    ship_fee        NUMERIC(10,0) NOT NULL DEFAULT 0,
    shipped_at      TIMESTAMPTZ,
    delivered_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_shipments_order   ON shop.shipments(order_id);
CREATE INDEX idx_shipments_invoice ON shop.shipments(invoice_no);

CREATE TABLE shop.shipment_tracking (
    tracking_id     BIGSERIAL PRIMARY KEY,
    shipment_id     BIGINT NOT NULL REFERENCES shop.shipments(shipment_id) ON DELETE CASCADE,
    status          shipment_status NOT NULL,
    location        VARCHAR(120),
    description     VARCHAR(255),
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =============================================================================
-- 5. 리뷰 / 감성분석
-- =============================================================================
CREATE TABLE shop.reviews (
    review_id       BIGSERIAL PRIMARY KEY,
    book_id         BIGINT NOT NULL REFERENCES shop.books(book_id) ON DELETE CASCADE,
    member_id       BIGINT NOT NULL REFERENCES shop.members(member_id) ON DELETE CASCADE,
    order_item_id   BIGINT REFERENCES shop.order_items(order_item_id),
    rating          SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    title           VARCHAR(200),
    content         TEXT NOT NULL,
    like_count      INTEGER NOT NULL DEFAULT 0,
    is_best         BOOLEAN NOT NULL DEFAULT false,
    is_blinded      BOOLEAN NOT NULL DEFAULT false,
    reply_content   TEXT,
    replied_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_reviews_book   ON shop.reviews(book_id, created_at DESC);
CREATE INDEX idx_reviews_member ON shop.reviews(member_id, created_at DESC);

CREATE TABLE shop.review_images (
    image_id        BIGSERIAL PRIMARY KEY,
    review_id       BIGINT NOT NULL REFERENCES shop.reviews(review_id) ON DELETE CASCADE,
    image_url       VARCHAR(255) NOT NULL,
    sort_order      SMALLINT NOT NULL DEFAULT 0
);

CREATE TABLE shop.review_likes (
    review_id       BIGINT NOT NULL REFERENCES shop.reviews(review_id) ON DELETE CASCADE,
    member_id       BIGINT NOT NULL REFERENCES shop.members(member_id) ON DELETE CASCADE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (review_id, member_id)
);

CREATE TABLE ai.review_sentiments (
    sentiment_id    BIGSERIAL PRIMARY KEY,
    review_id       BIGINT NOT NULL UNIQUE REFERENCES shop.reviews(review_id) ON DELETE CASCADE,
    book_id         BIGINT NOT NULL,
    label           sentiment_label NOT NULL,
    score           NUMERIC(6,4) NOT NULL,
    positive_prob   NUMERIC(6,4) NOT NULL DEFAULT 0,
    negative_prob   NUMERIC(6,4) NOT NULL DEFAULT 0,
    keywords        JSONB,
    model_version   VARCHAR(40) NOT NULL DEFAULT 'kosa-lr-v1',
    analyzed_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_sentiments_book  ON ai.review_sentiments(book_id, label);

-- =============================================================================
-- 6. 고객 지원 (공지 / Q&A / FAQ / 1:1 채팅)
-- =============================================================================
CREATE TABLE shop.notices (
    notice_id       BIGSERIAL PRIMARY KEY,
    category        VARCHAR(30) NOT NULL DEFAULT 'GENERAL',
    title           VARCHAR(250) NOT NULL,
    content         TEXT NOT NULL,
    is_pinned       BOOLEAN NOT NULL DEFAULT false,
    is_published    BOOLEAN NOT NULL DEFAULT true,
    view_count      INTEGER NOT NULL DEFAULT 0,
    author_id       BIGINT REFERENCES shop.members(member_id),
    published_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_notices_pub ON shop.notices(is_published, is_pinned DESC, published_at DESC);

CREATE TABLE shop.notice_attachments (
    attachment_id   BIGSERIAL PRIMARY KEY,
    notice_id       BIGINT NOT NULL REFERENCES shop.notices(notice_id) ON DELETE CASCADE,
    file_name       VARCHAR(255) NOT NULL,
    file_url        VARCHAR(255) NOT NULL,
    file_size       INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE shop.qna_questions (
    question_id     BIGSERIAL PRIMARY KEY,
    member_id       BIGINT NOT NULL REFERENCES shop.members(member_id) ON DELETE CASCADE,
    book_id         BIGINT REFERENCES shop.books(book_id) ON DELETE SET NULL,
    order_id        BIGINT REFERENCES shop.orders(order_id) ON DELETE SET NULL,
    category        VARCHAR(30) NOT NULL DEFAULT 'ETC',
    title           VARCHAR(250) NOT NULL,
    content         TEXT NOT NULL,
    status          qna_status NOT NULL DEFAULT 'WAITING',
    is_secret       BOOLEAN NOT NULL DEFAULT false,
    view_count      INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_qna_member ON shop.qna_questions(member_id, created_at DESC);
CREATE INDEX idx_qna_status ON shop.qna_questions(status, created_at DESC);

CREATE TABLE shop.qna_answers (
    answer_id       BIGSERIAL PRIMARY KEY,
    question_id     BIGINT NOT NULL REFERENCES shop.qna_questions(question_id) ON DELETE CASCADE,
    admin_id        BIGINT REFERENCES shop.members(member_id),
    content         TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE shop.faqs (
    faq_id          BIGSERIAL PRIMARY KEY,
    category        VARCHAR(30) NOT NULL DEFAULT 'GENERAL',
    question        VARCHAR(300) NOT NULL,
    answer          TEXT NOT NULL,
    sort_order      SMALLINT NOT NULL DEFAULT 0,
    is_active       BOOLEAN NOT NULL DEFAULT true,
    view_count      INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE shop.chat_rooms (
    room_id         BIGSERIAL PRIMARY KEY,
    room_uuid       UUID NOT NULL DEFAULT gen_random_uuid(),
    member_id       BIGINT NOT NULL REFERENCES shop.members(member_id) ON DELETE CASCADE,
    agent_id        BIGINT REFERENCES shop.members(member_id),
    subject         VARCHAR(200) NOT NULL DEFAULT '1:1 문의',
    status          chat_room_status NOT NULL DEFAULT 'OPEN',
    last_message    VARCHAR(500),
    last_message_at TIMESTAMPTZ,
    unread_user     INTEGER NOT NULL DEFAULT 0,
    unread_agent    INTEGER NOT NULL DEFAULT 0,
    satisfaction    SMALLINT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at       TIMESTAMPTZ
);
CREATE INDEX idx_chat_rooms_member ON shop.chat_rooms(member_id, created_at DESC);
CREATE INDEX idx_chat_rooms_status ON shop.chat_rooms(status, last_message_at DESC);

CREATE TABLE shop.chat_messages (
    message_id      BIGSERIAL PRIMARY KEY,
    room_id         BIGINT NOT NULL REFERENCES shop.chat_rooms(room_id) ON DELETE CASCADE,
    sender_id       BIGINT REFERENCES shop.members(member_id),
    sender_type     VARCHAR(10) NOT NULL DEFAULT 'USER',
    content         TEXT NOT NULL,
    attachment_url  VARCHAR(255),
    is_read         BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_chat_msg_room ON shop.chat_messages(room_id, created_at);

-- =============================================================================
-- 7. 프로모션 (쿠폰 / 포인트 / 배너)
-- =============================================================================
CREATE TABLE shop.coupons (
    coupon_id       BIGSERIAL PRIMARY KEY,
    code            VARCHAR(40) NOT NULL UNIQUE,
    name            VARCHAR(120) NOT NULL,
    coupon_type     coupon_type NOT NULL,
    discount_value  NUMERIC(10,2) NOT NULL,
    max_discount    NUMERIC(10,0),
    min_order_amount NUMERIC(12,0) NOT NULL DEFAULT 0,
    category_id     INTEGER REFERENCES shop.categories(category_id),
    total_quantity  INTEGER,
    issued_count    INTEGER NOT NULL DEFAULT 0,
    valid_from      TIMESTAMPTZ NOT NULL DEFAULT now(),
    valid_to        TIMESTAMPTZ NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE shop.member_coupons (
    member_coupon_id BIGSERIAL PRIMARY KEY,
    member_id       BIGINT NOT NULL REFERENCES shop.members(member_id) ON DELETE CASCADE,
    coupon_id       BIGINT NOT NULL REFERENCES shop.coupons(coupon_id) ON DELETE CASCADE,
    order_id        BIGINT REFERENCES shop.orders(order_id),
    is_used         BOOLEAN NOT NULL DEFAULT false,
    issued_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    used_at         TIMESTAMPTZ,
    expires_at      TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_member_coupons ON shop.member_coupons(member_id, is_used);

CREATE TABLE shop.point_histories (
    point_id        BIGSERIAL PRIMARY KEY,
    member_id       BIGINT NOT NULL REFERENCES shop.members(member_id) ON DELETE CASCADE,
    reason          point_reason NOT NULL,
    amount          INTEGER NOT NULL,
    balance_after   INTEGER NOT NULL,
    ref_id          BIGINT,
    memo            VARCHAR(200),
    expires_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_point_hist_member ON shop.point_histories(member_id, created_at DESC);

CREATE TABLE shop.banners (
    banner_id       BIGSERIAL PRIMARY KEY,
    position        VARCHAR(30) NOT NULL DEFAULT 'MAIN_TOP',
    title           VARCHAR(200) NOT NULL,
    image_url       VARCHAR(255) NOT NULL,
    link_url        VARCHAR(255),
    sort_order      SMALLINT NOT NULL DEFAULT 0,
    is_active       BOOLEAN NOT NULL DEFAULT true,
    starts_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    ends_at         TIMESTAMPTZ
);

-- =============================================================================
-- 8. AI 도메인 테이블
-- =============================================================================

-- 8-1. 모델 학습 실행 이력
CREATE TABLE ai.model_runs (
    run_id          BIGSERIAL PRIMARY KEY,
    model_name      VARCHAR(60) NOT NULL,
    model_version   VARCHAR(40) NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'RUNNING',
    row_count       INTEGER NOT NULL DEFAULT 0,
    metrics         JSONB,
    params          JSONB,
    artifact_path   VARCHAR(255),
    error_message   TEXT,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ
);
CREATE INDEX idx_model_runs ON ai.model_runs(model_name, started_at DESC);

-- 8-2. 협업 필터링 추천 결과 캐시
CREATE TABLE ai.recommendations (
    rec_id          BIGSERIAL PRIMARY KEY,
    member_id       BIGINT NOT NULL,
    book_id         BIGINT NOT NULL,
    score           NUMERIC(8,5) NOT NULL,
    algorithm       VARCHAR(30) NOT NULL DEFAULT 'ITEM_CF',
    rank            SMALLINT NOT NULL DEFAULT 0,
    model_version   VARCHAR(40) NOT NULL DEFAULT 'cf-v1',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_recs_member ON ai.recommendations(member_id, rank);
CREATE UNIQUE INDEX uq_recs ON ai.recommendations(member_id, book_id, algorithm);

-- 8-3. 상품 유사도 (item-item)
CREATE TABLE ai.book_similarities (
    book_id         BIGINT NOT NULL,
    similar_book_id BIGINT NOT NULL,
    similarity      NUMERIC(8,5) NOT NULL,
    algorithm       VARCHAR(30) NOT NULL DEFAULT 'COSINE',
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (book_id, similar_book_id, algorithm)
);
CREATE INDEX idx_book_sim ON ai.book_similarities(book_id, similarity DESC);

-- 8-4. 일별 매출 집계 (ETL 결과)
CREATE TABLE ai.sales_daily (
    stat_date       DATE PRIMARY KEY,
    order_count     INTEGER NOT NULL DEFAULT 0,
    item_count      INTEGER NOT NULL DEFAULT 0,
    gross_amount    NUMERIC(14,0) NOT NULL DEFAULT 0,
    discount_amount NUMERIC(14,0) NOT NULL DEFAULT 0,
    net_amount      NUMERIC(14,0) NOT NULL DEFAULT 0,
    cancel_amount   NUMERIC(14,0) NOT NULL DEFAULT 0,
    new_member_cnt  INTEGER NOT NULL DEFAULT 0,
    visitor_cnt     INTEGER NOT NULL DEFAULT 0,
    avg_order_value NUMERIC(12,2) NOT NULL DEFAULT 0,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 8-5. 판매 예측
CREATE TABLE ai.sales_forecasts (
    forecast_id     BIGSERIAL PRIMARY KEY,
    target_date     DATE NOT NULL,
    scope           VARCHAR(20) NOT NULL DEFAULT 'TOTAL',
    scope_key       VARCHAR(40),
    predicted_amount NUMERIC(14,0) NOT NULL,
    lower_bound     NUMERIC(14,0),
    upper_bound     NUMERIC(14,0),
    model_version   VARCHAR(40) NOT NULL DEFAULT 'ridge-ts-v1',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (target_date, scope, scope_key, model_version)
);

-- 8-6. 고객 세그먼트 (RFM + KMeans)
CREATE TABLE ai.customer_segments (
    member_id       BIGINT PRIMARY KEY,
    recency_days    INTEGER NOT NULL DEFAULT 999,
    frequency       INTEGER NOT NULL DEFAULT 0,
    monetary        NUMERIC(14,0) NOT NULL DEFAULT 0,
    r_score         SMALLINT NOT NULL DEFAULT 1,
    f_score         SMALLINT NOT NULL DEFAULT 1,
    m_score         SMALLINT NOT NULL DEFAULT 1,
    rfm_segment     VARCHAR(30) NOT NULL DEFAULT 'NEW',
    cluster_id      SMALLINT,
    cluster_label   VARCHAR(40),
    ltv_estimate    NUMERIC(14,0),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_segments_rfm ON ai.customer_segments(rfm_segment);

-- 8-7. 이탈 예측
CREATE TABLE ai.churn_predictions (
    member_id       BIGINT PRIMARY KEY,
    churn_probability NUMERIC(6,4) NOT NULL,
    risk_level      VARCHAR(10) NOT NULL DEFAULT 'LOW',
    top_features    JSONB,
    model_version   VARCHAR(40) NOT NULL DEFAULT 'churn-lr-v1',
    predicted_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_churn_risk ON ai.churn_predictions(risk_level, churn_probability DESC);

-- 8-8. 연관 구매 규칙 (장바구니 분석)
CREATE TABLE ai.association_rules (
    rule_id         BIGSERIAL PRIMARY KEY,
    antecedent      BIGINT NOT NULL,
    consequent      BIGINT NOT NULL,
    support         NUMERIC(8,6) NOT NULL,
    confidence      NUMERIC(8,6) NOT NULL,
    lift            NUMERIC(10,4) NOT NULL,
    pair_count      INTEGER NOT NULL DEFAULT 0,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (antecedent, consequent)
);
CREATE INDEX idx_assoc_ante ON ai.association_rules(antecedent, lift DESC);

-- =============================================================================
-- 9. 트리거 & 함수
-- =============================================================================

-- 9-1. updated_at 자동 갱신
CREATE OR REPLACE FUNCTION shop.fn_set_updated_at() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_members_updated   BEFORE UPDATE ON shop.members
    FOR EACH ROW EXECUTE FUNCTION shop.fn_set_updated_at();
CREATE TRIGGER trg_books_updated     BEFORE UPDATE ON shop.books
    FOR EACH ROW EXECUTE FUNCTION shop.fn_set_updated_at();
CREATE TRIGGER trg_orders_updated    BEFORE UPDATE ON shop.orders
    FOR EACH ROW EXECUTE FUNCTION shop.fn_set_updated_at();
CREATE TRIGGER trg_reviews_updated   BEFORE UPDATE ON shop.reviews
    FOR EACH ROW EXECUTE FUNCTION shop.fn_set_updated_at();
CREATE TRIGGER trg_notices_updated   BEFORE UPDATE ON shop.notices
    FOR EACH ROW EXECUTE FUNCTION shop.fn_set_updated_at();

-- 9-2. 도서 검색 벡터 갱신
CREATE OR REPLACE FUNCTION shop.fn_books_search_vector() RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('simple', coalesce(NEW.title, '')), 'A') ||
        setweight(to_tsvector('simple', coalesce(NEW.subtitle, '')), 'B') ||
        setweight(to_tsvector('simple', coalesce(NEW.summary, '')), 'C');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_books_search_vector BEFORE INSERT OR UPDATE OF title, subtitle, summary
    ON shop.books FOR EACH ROW EXECUTE FUNCTION shop.fn_books_search_vector();

-- 9-3. 리뷰 작성/삭제 시 도서 평점 재계산
CREATE OR REPLACE FUNCTION shop.fn_recalc_book_rating() RETURNS TRIGGER AS $$
DECLARE
    v_book_id BIGINT;
BEGIN
    v_book_id := COALESCE(NEW.book_id, OLD.book_id);
    UPDATE shop.books b
       SET rating_avg = COALESCE(sub.avg_rating, 0),
           review_count = COALESCE(sub.cnt, 0)
      FROM (
            SELECT ROUND(AVG(rating)::numeric, 2) AS avg_rating, COUNT(*) AS cnt
              FROM shop.reviews
             WHERE book_id = v_book_id AND is_blinded = false
           ) sub
     WHERE b.book_id = v_book_id;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_reviews_rating AFTER INSERT OR UPDATE OR DELETE ON shop.reviews
    FOR EACH ROW EXECUTE FUNCTION shop.fn_recalc_book_rating();

-- 9-4. 주문번호 생성 함수
CREATE OR REPLACE FUNCTION shop.fn_generate_order_no() RETURNS VARCHAR AS $$
DECLARE
    v_seq BIGINT;
BEGIN
    SELECT nextval('shop.orders_order_id_seq') INTO v_seq;
    RETURN to_char(now(), 'YYYYMMDD') || lpad(v_seq::text, 8, '0');
END;
$$ LANGUAGE plpgsql;

-- 9-5. 재고 차감 (동시성 안전)
CREATE OR REPLACE FUNCTION shop.fn_decrease_stock(p_book_id BIGINT, p_qty INTEGER)
RETURNS INTEGER AS $$
DECLARE
    v_after INTEGER;
BEGIN
    UPDATE shop.books
       SET stock_qty = stock_qty - p_qty,
           sales_count = sales_count + p_qty,
           status = CASE WHEN stock_qty - p_qty <= 0 THEN 'SOLDOUT'::book_status ELSE status END
     WHERE book_id = p_book_id AND stock_qty >= p_qty
     RETURNING stock_qty INTO v_after;

    IF v_after IS NULL THEN
        RAISE EXCEPTION 'OUT_OF_STOCK: book_id=%', p_book_id;
    END IF;

    INSERT INTO log.stock_histories(book_id, change_qty, after_qty, reason)
    VALUES (p_book_id, -p_qty, v_after, 'ORDER');

    RETURN v_after;
END;
$$ LANGUAGE plpgsql;

-- 9-6. 회원 등급 재계산
CREATE OR REPLACE FUNCTION shop.fn_refresh_member_grade(p_member_id BIGINT)
RETURNS SMALLINT AS $$
DECLARE
    v_amount NUMERIC;
    v_grade  SMALLINT;
BEGIN
    SELECT COALESCE(SUM(total_amount), 0) INTO v_amount
      FROM shop.orders
     WHERE member_id = p_member_id
       AND status IN ('PAID','PREPARING','SHIPPING','DELIVERED','CONFIRMED')
       AND ordered_at >= now() - interval '6 months';

    SELECT grade_id INTO v_grade
      FROM shop.member_grades
     WHERE min_amount <= v_amount
     ORDER BY min_amount DESC
     LIMIT 1;

    UPDATE shop.members SET grade_id = COALESCE(v_grade, 1), total_paid = v_amount
     WHERE member_id = p_member_id;

    RETURN v_grade;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- 10. 뷰 (관리자 대시보드/분석용)
-- =============================================================================
CREATE OR REPLACE VIEW ai.v_order_matrix AS
SELECT o.member_id,
       oi.book_id,
       SUM(oi.quantity)::int AS qty,
       MAX(o.ordered_at)     AS last_ordered_at
  FROM shop.orders o
  JOIN shop.order_items oi ON oi.order_id = o.order_id
 WHERE o.member_id IS NOT NULL
   AND o.status IN ('PAID','PREPARING','SHIPPING','DELIVERED','CONFIRMED')
 GROUP BY o.member_id, oi.book_id;

CREATE OR REPLACE VIEW ai.v_member_features AS
SELECT m.member_id,
       m.created_at,
       m.grade_id,
       COALESCE(agg.order_cnt, 0)        AS order_cnt,
       COALESCE(agg.total_amount, 0)     AS total_amount,
       COALESCE(agg.avg_amount, 0)       AS avg_amount,
       COALESCE(agg.distinct_books, 0)   AS distinct_books,
       COALESCE(rv.review_cnt, 0)        AS review_cnt,
       COALESCE(rv.avg_rating, 0)        AS avg_rating,
       EXTRACT(DAY FROM now() - COALESCE(agg.last_ordered_at, m.created_at))::int AS recency_days,
       EXTRACT(DAY FROM now() - COALESCE(m.last_login_at, m.created_at))::int     AS login_recency_days,
       EXTRACT(DAY FROM now() - m.created_at)::int AS tenure_days
  FROM shop.members m
  LEFT JOIN (
        SELECT o.member_id,
               COUNT(DISTINCT o.order_id)        AS order_cnt,
               SUM(o.total_amount)               AS total_amount,
               AVG(o.total_amount)               AS avg_amount,
               COUNT(DISTINCT oi.book_id)        AS distinct_books,
               MAX(o.ordered_at)                 AS last_ordered_at
          FROM shop.orders o
          JOIN shop.order_items oi ON oi.order_id = o.order_id
         WHERE o.status IN ('PAID','PREPARING','SHIPPING','DELIVERED','CONFIRMED')
         GROUP BY o.member_id
  ) agg ON agg.member_id = m.member_id
  LEFT JOIN (
        SELECT member_id, COUNT(*) AS review_cnt, AVG(rating) AS avg_rating
          FROM shop.reviews GROUP BY member_id
  ) rv ON rv.member_id = m.member_id
 WHERE m.status <> 'WITHDRAWN';

CREATE OR REPLACE VIEW shop.v_dashboard_today AS
SELECT
    (SELECT COUNT(*) FROM shop.orders WHERE ordered_at::date = CURRENT_DATE)                      AS today_orders,
    (SELECT COALESCE(SUM(total_amount),0) FROM shop.orders
       WHERE ordered_at::date = CURRENT_DATE AND status <> 'CANCELLED')                           AS today_sales,
    (SELECT COUNT(*) FROM shop.members WHERE created_at::date = CURRENT_DATE)                     AS today_members,
    (SELECT COUNT(*) FROM shop.reviews WHERE created_at::date = CURRENT_DATE)                      AS today_reviews,
    (SELECT COUNT(*) FROM shop.qna_questions WHERE status = 'WAITING')                             AS waiting_qna,
    (SELECT COUNT(*) FROM shop.chat_rooms WHERE status = 'OPEN')                                   AS open_chats,
    (SELECT COUNT(*) FROM shop.books WHERE stock_qty <= safety_stock AND status = 'SALE')          AS low_stock_books;

-- =============================================================================
-- 11. 초기 데이터 (등급)
-- =============================================================================
INSERT INTO shop.member_grades (grade_code, grade_name, min_amount, discount_rate, point_rate, free_ship_limit, sort_order)
VALUES ('BRONZE', '브론즈',       0,       0.0, 1.0, 20000, 1),
       ('SILVER', '실버',   100000,       1.0, 1.5, 20000, 2),
       ('GOLD',   '골드',   300000,       2.0, 2.0, 15000, 3),
       ('PLATINUM','플래티넘', 700000,    3.0, 2.5,     0, 4),
       ('DIAMOND','다이아몬드',1500000,   5.0, 3.0,     0, 5)
ON CONFLICT (grade_code) DO NOTHING;

-- =============================================================================
-- 완료
-- =============================================================================
