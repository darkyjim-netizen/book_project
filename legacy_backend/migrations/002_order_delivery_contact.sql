-- 주문에 배송 연락처와 우편번호를 보관합니다.
-- 기존 DB에 한 번 실행하면 됩니다. 여러 번 실행해도 결과는 같습니다.

ALTER TABLE orders ADD COLUMN IF NOT EXISTS receiver_phone VARCHAR(30);
ALTER TABLE orders ADD COLUMN IF NOT EXISTS postal_code    VARCHAR(10);
