-- 환불·반품 더미데이터 되돌리기 (20261119_seed_refunds.sql 로 넣은 것만 원래대로)
-- 적용: psql -U postgres -d book -f database/20261119_seed_refunds_rollback.sql
BEGIN;

DELETE FROM shop.refunds WHERE reason_text LIKE '[더미]%';

UPDATE shop.payments p
   SET status = t.prev_pay_status,
       approved_at = t.prev_approved_at,
       cancelled_amount = 0,
       cancelled_at = NULL
  FROM log.dummy_refund_targets t
 WHERE p.payment_id = (SELECT payment_id FROM shop.payments WHERE order_id = t.order_id ORDER BY payment_id DESC LIMIT 1);

UPDATE shop.orders o SET status = t.prev_status
  FROM log.dummy_refund_targets t WHERE o.order_id = t.order_id;
UPDATE shop.order_items i SET status = t.prev_status
  FROM log.dummy_refund_targets t WHERE i.order_id = t.order_id AND t.kind IN ('RETURN_REQ', 'RETURNED');

DROP TABLE log.dummy_refund_targets;

COMMIT;
