-- 토스페이먼츠 결제 연동에 필요한 orders 테이블 변경 (PostgreSQL)
-- 기존 DB에 한 번만 실행하면 됩니다. 여러 번 실행해도 결과는 같습니다.
-- order_status_histories 테이블은 서버를 시작할 때 자동으로 만들어집니다.
--
-- 실행 예: psql -U <DB_USER> -d <DB_NAME> -f migrations/001_toss_payment.sql

BEGIN;

ALTER TABLE orders ADD COLUMN IF NOT EXISTS order_number   VARCHAR(64);
ALTER TABLE orders ADD COLUMN IF NOT EXISTS status         VARCHAR(20) NOT NULL DEFAULT 'pending';
ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_method VARCHAR(20) NOT NULL DEFAULT 'test';
ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_key    VARCHAR(200);
ALTER TABLE orders ADD COLUMN IF NOT EXISTS paid_at        TIMESTAMPTZ;

-- 결제 연동 이전의 주문은 모두 테스트 결제로 완료된 주문이므로 결제 완료로 표시합니다.
-- (주문번호가 아직 없는 행만 대상이므로 아래 주문번호 채우기보다 먼저 실행해야 합니다.)
UPDATE orders
   SET status = 'paid', paid_at = created_at
 WHERE order_number IS NULL AND payment_status = 'test_paid';

-- 기존 주문에도 주문번호를 채웁니다.
UPDATE orders
   SET order_number = 'ORD-' || to_char(created_at, 'YYYYMMDD') || '-' || lpad(id::text, 10, '0')
 WHERE order_number IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS ix_orders_order_number ON orders (order_number);
CREATE INDEX        IF NOT EXISTS ix_orders_status       ON orders (status);

COMMIT;
