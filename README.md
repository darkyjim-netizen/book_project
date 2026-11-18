# 북적북적 웹 프로젝트

북적북적은 FastAPI와 Vue 3로 구성한 도서 쇼핑몰입니다.

## 폴더 구성

- `main.py`: 통합 FastAPI 실행점
- `team_backend/app/`: 현재 백엔드의 API, 서비스, DB 모델과 설정
- `team_backend/database/`: 현재 PostgreSQL 스키마와 초기 데이터
- `vue/src/views/`: 로그인, 계정 대시보드, 관리자 회원 관리 화면
- `vue/src/storefront/pages/`: 북적북적 쇼핑몰의 페이지별 Vue 화면
- `vue/src/router/index.js`: Vue Router 주소 설정
- `vue/public/styles/storefront/`, `vue/public/assets/`: 쇼핑몰 스타일과 이미지
- `tests/`: 통합 백엔드의 테스트
- `legacy_backend/`: 이전 백엔드와 해당 DB 스크립트, 템플릿, 검증 자료

## 실행 준비

1. PostgreSQL에서 사용할 데이터베이스를 준비합니다. 기본값은 `book`입니다.
2. `team_backend/.env.example`을 저장소 루트의 `.env`로 복사한 뒤 DB 설정과 `SECRET_KEY`를 설정합니다.
3. FastAPI를 자동 재시작 모드로 실행합니다.

```powershell
cd bookbook
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\start-backend.cmd
```

4. 새 터미널에서 Vue 앱을 실행합니다.

```powershell
cd bookbook\vue
npm install
npm run dev
```

쇼핑몰은 `http://localhost:5173/main`에서 열립니다. Vue 앱의 회원 인증 API는 Vite 프록시를 통해 FastAPI의 `http://127.0.0.1:8000`으로 연결됩니다.

## 저장 후 바로 반영

`start-backend.cmd`와 `npm run dev` 터미널을 켜 둔 채 `http://localhost:5173/main`을 열어 작업합니다. 백엔드 실행 파일은 가상환경을 활성화하지 않아도 프로젝트의 `.venv` Python을 직접 사용합니다. Python 변경은 Uvicorn이 자동 재시작하고, `src/`의 Vue 파일은 Vite가 즉시 반영합니다. `public/`의 스타일이나 이미지를 수정한 뒤에는 브라우저를 새로고침하세요.

## 메인 테스트 도서 1,000권 채우기

기존 도서는 건드리지 않고 부족한 수만 추가합니다. 기준 카테고리·출판사·저자 데이터가 입력된 뒤 아래를 한 번 실행하세요.

```powershell
python -m team_backend.scripts.seed_books_to_1000
```

메인 페이지의 추천·신간은 각각 최대 30권을 DB에서 표시하며, 상단 슬라이더도 DB 조회 결과의 앞 3권을 사용합니다. 창으로 다시 돌아오거나 30초마다 자동으로 DB 목록을 다시 불러옵니다.

## API와 데모 범위

통합 백엔드의 API는 `http://localhost:8000/docs`에서 확인할 수 있습니다. 쇼핑몰의 도서·리뷰·주소 검색은 `/api/v1` API를 사용합니다. 쇼핑몰의 장바구니·찜과 데모 상품 관리 데이터는 브라우저에 저장합니다.
