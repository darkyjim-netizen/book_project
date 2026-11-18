# 이전 백엔드

통합 이전의 FastAPI 소스와 이에 해당하는 DB 스크립트, 결제 템플릿을 보관합니다. 현재 서버는 저장소 루트의 `main:app`으로 실행하며 `team_backend/database/schema.sql`을 사용합니다.

이전 결제 통합 테스트는 `tests/test_payment_flow.py`에 보관합니다. 당시 테스트의 `conftest.py`와 구형 인증 모듈의 `jwt` 의존성이 현재 환경에 없어 별도 복원 없이 실행할 수 없습니다. 루트에서 기본 `pytest` 실행은 현재 백엔드의 테스트를 수집합니다.
