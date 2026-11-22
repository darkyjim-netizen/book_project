-- =============================================================================
-- 환불·반품 더미데이터 (발표/화면 확인용)
--   1) 기존 취소(CANCELLED) 주문  → 전액 환불 기록 생성
--   2) 배송완료·구매확정 주문 25건 → 부분 환불 (결제 상태 PARTIAL_CANCELLED)
--   3) 배송완료 주문 15건          → 반품 신청(RETURN_REQ), 환불 전
--   4) 배송완료 주문 10건          → 반품 완료(RETURNED) + 환불(반품 배송비 3,000원 차감)
--
-- 더미로 바꾼 주문은 log.dummy_refund_targets 에 원래 상태와 함께 기록하고,
-- 환불 사유(reason_text)는 '[더미]'로 시작한다.
-- 되돌리기: psql -U postgres -d book -f database/20261119_seed_refunds_rollback.sql
-- 적용:     psql -U postgres -d book -f database/20261119_seed_refunds.sql
-- =============================================================================
BEGIN;

SELECT setseed(0.42);  -- 실행할 때마다 같은 주문이 뽑히도록 고정

CREATE TABLE IF NOT EXISTS log.dummy_refund_targets (
    order_id        BIGINT PRIMARY KEY,
    kind            VARCHAR(20) NOT NULL,          -- CANCEL_REFUND / PARTIAL / RETURN_REQ / RETURNED
    prev_status     shop.order_status NOT NULL,
    prev_pay_status shop.payment_status,
    prev_approved_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 이미 한 번 넣었다면 중복 실행을 막는다.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM log.dummy_refund_targets) THEN
        RAISE EXCEPTION '환불 더미데이터가 이미 들어가 있습니다. 먼저 rollback 스크립트를 실행하세요.';
    END IF;
END $$;

-- 처리자로 기록할 관리자 (없으면 NULL)
CREATE TEMP TABLE _admin ON COMMIT DROP AS
SELECT (SELECT member_id FROM shop.members WHERE role = 'ADMIN' ORDER BY member_id LIMIT 1) AS admin_id;

-- 주문별 대표 결제(가장 최근 결제)
CREATE TEMP TABLE _pay ON COMMIT DROP AS
SELECT DISTINCT ON (order_id) payment_id, order_id, status, amount, approved_at
  FROM shop.payments
 ORDER BY order_id, payment_id DESC;

-- -----------------------------------------------------------------------------
-- 대상 주문 고르기
-- -----------------------------------------------------------------------------
INSERT INTO log.dummy_refund_targets (order_id, kind, prev_status, prev_pay_status, prev_approved_at)
SELECT o.order_id, 'CANCEL_REFUND', o.status, p.status, p.approved_at
  FROM shop.orders o JOIN _pay p ON p.order_id = o.order_id
 WHERE o.status = 'CANCELLED' AND o.paid_at IS NOT NULL AND p.amount > 0
   AND NOT EXISTS (SELECT 1 FROM shop.refunds r WHERE r.order_id = o.order_id);

INSERT INTO log.dummy_refund_targets (order_id, kind, prev_status, prev_pay_status, prev_approved_at)
SELECT order_id, 'PARTIAL', status, pay_status, approved_at FROM (
    SELECT o.order_id, o.status, p.status AS pay_status, p.approved_at
      FROM shop.orders o JOIN _pay p ON p.order_id = o.order_id
     WHERE o.status IN ('DELIVERED', 'CONFIRMED') AND p.status = 'PAID' AND o.total_amount >= 20000
       AND NOT EXISTS (SELECT 1 FROM shop.refunds r WHERE r.order_id = o.order_id)
     ORDER BY random() LIMIT 25
) t;

INSERT INTO log.dummy_refund_targets (order_id, kind, prev_status, prev_pay_status, prev_approved_at)
SELECT order_id, kind, status, pay_status, approved_at FROM (
    SELECT o.order_id, o.status, p.status AS pay_status, p.approved_at,
           CASE WHEN row_number() OVER (ORDER BY random()) <= 15 THEN 'RETURN_REQ' ELSE 'RETURNED' END AS kind
      FROM shop.orders o JOIN _pay p ON p.order_id = o.order_id
     WHERE o.status = 'DELIVERED' AND p.status = 'PAID' AND o.total_amount > 3000
       AND o.order_id NOT IN (SELECT order_id FROM log.dummy_refund_targets)
     ORDER BY random() LIMIT 25
) t;

-- 사유 코드/문구 후보
CREATE TEMP TABLE _reason ON COMMIT DROP AS
SELECT * FROM (VALUES
    (1, 'CHANGE_MIND',    '단순 변심'),
    (2, 'WRONG_ORDER',    '주문 실수(다른 책 주문)'),
    (3, 'DELAY',          '배송 지연'),
    (4, 'DEFECT',         '파본·인쇄 불량'),
    (5, 'WRONG_DELIVERY', '다른 상품 배송'),
    (6, 'ETC',            '기타')
) v(no, code, label);

-- -----------------------------------------------------------------------------
-- 1) 취소 주문 전액 환불
-- -----------------------------------------------------------------------------
INSERT INTO shop.refunds (order_id, payment_id, refund_amount, point_restore, reason_code, reason_text,
                          processed_by, created_at, completed_at)
SELECT o.order_id, p.payment_id, p.amount, o.point_used, r.code, '[더미] 주문 취소 환불 - ' || r.label,
       NULL, COALESCE(o.cancelled_at, o.ordered_at + interval '1 day'),
       COALESCE(o.cancelled_at, o.ordered_at + interval '1 day') + interval '10 minutes'
  FROM log.dummy_refund_targets t
  JOIN shop.orders o ON o.order_id = t.order_id
  JOIN _pay p ON p.order_id = o.order_id
  JOIN _reason r ON r.no = 1 + (o.order_id % 3)          -- 취소는 변심/주문실수/지연 위주
 WHERE t.kind = 'CANCEL_REFUND';

UPDATE shop.payments p
   SET status = 'CANCELLED',
       approved_at = COALESCE(p.approved_at, o.paid_at),
       cancelled_amount = p.amount,
       cancelled_at = COALESCE(o.cancelled_at, o.ordered_at + interval '1 day') + interval '10 minutes'
  FROM log.dummy_refund_targets t JOIN shop.orders o ON o.order_id = t.order_id
 WHERE t.kind = 'CANCEL_REFUND' AND p.payment_id = (SELECT payment_id FROM _pay WHERE order_id = t.order_id);

-- -----------------------------------------------------------------------------
-- 2) 부분 환불 (결제금액의 20~50%, 100원 단위)
-- -----------------------------------------------------------------------------
CREATE TEMP TABLE _partial ON COMMIT DROP AS
SELECT t.order_id, p.payment_id,
       (round(p.amount * (0.2 + random() * 0.3) / 100) * 100)::numeric AS amt,
       o.ordered_at + interval '4 days' + (random() * interval '3 days') AS at
  FROM log.dummy_refund_targets t
  JOIN shop.orders o ON o.order_id = t.order_id
  JOIN _pay p ON p.order_id = t.order_id
 WHERE t.kind = 'PARTIAL';

INSERT INTO shop.refunds (order_id, payment_id, refund_amount, point_restore, reason_code, reason_text,
                          processed_by, created_at, completed_at)
SELECT x.order_id, x.payment_id, x.amt, 0, r.code, '[더미] 일부 상품 환불 - ' || r.label,
       (SELECT admin_id FROM _admin), x.at, x.at + interval '1 hour'
  FROM _partial x JOIN _reason r ON r.no = 4 + (x.order_id % 3);   -- 파본/오배송/기타

UPDATE shop.payments p
   SET status = 'PARTIAL_CANCELLED', cancelled_amount = x.amt, cancelled_at = x.at + interval '1 hour'
  FROM _partial x WHERE p.payment_id = x.payment_id;

-- -----------------------------------------------------------------------------
-- 3) 반품 신청 (아직 환불 전)
-- -----------------------------------------------------------------------------
UPDATE shop.orders o SET status = 'RETURN_REQ'
  FROM log.dummy_refund_targets t WHERE t.order_id = o.order_id AND t.kind = 'RETURN_REQ';
UPDATE shop.order_items i SET status = 'RETURN_REQ'
  FROM log.dummy_refund_targets t WHERE t.order_id = i.order_id AND t.kind = 'RETURN_REQ';

-- -----------------------------------------------------------------------------
-- 4) 반품 완료 + 환불 (반품 배송비 3,000원 차감)
-- -----------------------------------------------------------------------------
INSERT INTO shop.refunds (order_id, payment_id, refund_amount, point_restore, reason_code, reason_text,
                          processed_by, created_at, completed_at)
SELECT o.order_id, p.payment_id, p.amount - 3000, o.point_used, r.code,
       '[더미] 반품 환불(반품 배송비 3,000원 차감) - ' || r.label,
       (SELECT admin_id FROM _admin),
       COALESCE(o.delivered_at, o.ordered_at + interval '2 days') + interval '3 days',
       COALESCE(o.delivered_at, o.ordered_at + interval '2 days') + interval '5 days'
  FROM log.dummy_refund_targets t
  JOIN shop.orders o ON o.order_id = t.order_id
  JOIN _pay p ON p.order_id = o.order_id
  JOIN _reason r ON r.no = CASE WHEN o.order_id % 2 = 0 THEN 1 ELSE 4 END   -- 변심/파본
 WHERE t.kind = 'RETURNED';

UPDATE shop.payments p
   SET status = 'CANCELLED', cancelled_amount = p.amount - 3000,
       cancelled_at = COALESCE(o.delivered_at, o.ordered_at + interval '2 days') + interval '5 days'
  FROM log.dummy_refund_targets t JOIN shop.orders o ON o.order_id = t.order_id
 WHERE t.kind = 'RETURNED' AND p.payment_id = (SELECT payment_id FROM _pay WHERE order_id = t.order_id);

UPDATE shop.orders o SET status = 'RETURNED'
  FROM log.dummy_refund_targets t WHERE t.order_id = o.order_id AND t.kind = 'RETURNED';
UPDATE shop.order_items i SET status = 'RETURNED'
  FROM log.dummy_refund_targets t WHERE t.order_id = i.order_id AND t.kind = 'RETURNED';

-- 결과 요약
SELECT kind, COUNT(*) AS orders FROM log.dummy_refund_targets GROUP BY kind ORDER BY kind;
SELECT COUNT(*) AS refunds, SUM(refund_amount) AS total_refund FROM shop.refunds WHERE reason_text LIKE '[더미]%';

COMMIT;
