-- 감정분석 3클래스(긍정/중립/부정) 대응: ai.review_sentiments 에 neutral_prob 추가
-- 적용 전 백업:  pg_dump -U postgres -d book -n ai -n shop -Fc -f book_before_neutral.dump
-- 적용:          psql -U postgres -d book -f database/20261117_add_neutral_prob.sql
-- 되돌리기:      ALTER TABLE ai.review_sentiments DROP COLUMN neutral_prob;
--               (제약조건 ck_review_sentiments_prob 도 함께 삭제됨)
--
-- 설계 메모
--  * positive_prob / negative_prob 와 같은 NUMERIC(6,4) 를 쓴다.
--  * NULL 허용: "아직 3클래스 모델로 분석하지 않은 행"을 0 으로 위장하지 않기 위해서다.
--    (현재 이 테이블은 0행이라 기존 데이터 영향은 없다.)
--  * label enum(shop.sentiment_label) 에는 이미 NEUTRAL 이 있어 변경하지 않는다.

BEGIN;

ALTER TABLE ai.review_sentiments
    ADD COLUMN IF NOT EXISTS neutral_prob NUMERIC(6,4);

COMMENT ON COLUMN ai.review_sentiments.neutral_prob IS
    '중립 감정 확률 (0~1). NULL = 3클래스 모델로 아직 분석하지 않음';

-- 세 확률이 0~1 범위인지 검사 (neutral 은 NULL 허용)
ALTER TABLE ai.review_sentiments
    ADD CONSTRAINT ck_review_sentiments_prob CHECK (
        positive_prob BETWEEN 0 AND 1
        AND negative_prob BETWEEN 0 AND 1
        AND (neutral_prob IS NULL OR neutral_prob BETWEEN 0 AND 1)
    );

COMMIT;

-- 확인용: 세 확률의 합이 약 1 인지 (부동소수점/반올림 오차 0.01 허용)
-- SELECT review_id, positive_prob, neutral_prob, negative_prob
--   FROM ai.review_sentiments
--  WHERE neutral_prob IS NOT NULL
--    AND abs(positive_prob + neutral_prob + negative_prob - 1) > 0.01;
