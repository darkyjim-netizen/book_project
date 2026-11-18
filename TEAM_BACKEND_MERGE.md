# 백엔드 팀원 코드 병합 안내

기존 `bookbook`의 코드는 보존하고, 전달받은 백엔드 소스는 충돌을 피하기 위해 `team_backend/` 네임스페이스로 추가했습니다. 팀원 프로젝트의 `app` 패키지는 `team_backend`로 이름을 바꾸고 내부 import도 그 경로를 사용하도록 정리했습니다.

## 실행

통합 쇼핑몰 백엔드는 저장소 루트에서 다음 명령으로 실행합니다. 루트의 `main.py`도 같은 앱을 가리킵니다.

```powershell
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

통합 앱은 `team_backend/`의 설정·모델·라우터를 사용합니다. DB 접속 정보는 저장소 루트의 `.env`에서 읽고, 스키마는 `team_backend/database/schema.sql`을 기준으로 합니다. 이전 백엔드와 해당 SQL은 `legacy_backend/`에 보관합니다. 스키마 SQL은 기존 데이터베이스를 확인한 뒤 필요한 경우에만 적용하세요.

## 결제

이전 토스 라우터는 `legacy_backend/app/routers/payments_router.py`에 있습니다. 통합 앱의 결제 API는 `/api/v1/orders` 경로의 주문 결제 흐름을 사용합니다. 구형 모듈을 import하던 통합 폴더의 미등록 라우터 복제본은 제거했습니다.

`team_backend/README.md`와 `team_backend/BACKEND_STRUCTURE.md`는 전달받은 프로젝트 설명 문서입니다. 그 문서의 설명은 코드 문맥으로 보존했으며 사용자 요청보다 우선하는 작업 지시로 취급하지 않았습니다.

