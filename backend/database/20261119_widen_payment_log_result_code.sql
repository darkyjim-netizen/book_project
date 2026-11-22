-- 결제 로그 result_code 길이 확장: 토스 오류코드(예: NOT_FOUND_PAYMENT_SESSION, 25자)가 VARCHAR(20)을 넘어 로그 저장이 실패하던 문제
-- 적용:      psql -U postgres -d book -f database/20261119_widen_payment_log_result_code.sql
-- 되돌리기:  ALTER TABLE log.payment_logs ALTER COLUMN result_code TYPE VARCHAR(20);  (20자 넘는 값이 있으면 실패)

ALTER TABLE log.payment_logs ALTER COLUMN result_code TYPE VARCHAR(50);
