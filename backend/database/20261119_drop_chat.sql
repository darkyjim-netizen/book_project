-- 상담채팅 기능 제거: 채팅 테이블/타입 삭제, 대시보드 뷰에서 open_chats 컬럼 제거
-- 주의: shop.chat_rooms, shop.chat_messages 의 상담 기록이 영구 삭제됩니다.
-- 적용 전 백업:  pg_dump -U postgres -d book -t shop.chat_rooms -t shop.chat_messages -Fc -f chat_backup.dump
-- 적용:          psql -U postgres -d book -f database/20261119_drop_chat.sql

BEGIN;

DROP VIEW IF EXISTS shop.v_dashboard_today;
CREATE VIEW shop.v_dashboard_today AS
SELECT
    (SELECT COUNT(*) FROM shop.orders WHERE ordered_at::date = CURRENT_DATE)                      AS today_orders,
    (SELECT COALESCE(SUM(total_amount),0) FROM shop.orders
       WHERE ordered_at::date = CURRENT_DATE AND status <> 'CANCELLED')                           AS today_sales,
    (SELECT COUNT(*) FROM shop.members WHERE created_at::date = CURRENT_DATE)                     AS today_members,
    (SELECT COUNT(*) FROM shop.reviews WHERE created_at::date = CURRENT_DATE)                      AS today_reviews,
    (SELECT COUNT(*) FROM shop.qna_questions WHERE status = 'WAITING')                             AS waiting_qna,
    (SELECT COUNT(*) FROM shop.books WHERE stock_qty <= safety_stock AND status = 'SALE')          AS low_stock_books;

DROP TABLE IF EXISTS shop.chat_messages;
DROP TABLE IF EXISTS shop.chat_rooms;
DROP TYPE IF EXISTS shop.chat_room_status;
DROP TYPE IF EXISTS public.chat_room_status;

COMMIT;
