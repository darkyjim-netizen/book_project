# 북적북적 웹 프로젝트

`frontend-vue`의 북적북적 쇼핑몰 디자인을 FastAPI 회원 관리 백엔드와 Vue 3 앱에 합친 프로젝트입니다.

## 폴더 구성

- `main.py`, `app/`: FastAPI 세션 인증, 회원 CRUD, 관리자 회원 관리 API
- `vue/src/`: Vue 3 + Vite 앱. 로그인, 회원가입, 계정 대시보드, 마이페이지, 관리자 회원 관리 화면
- `vue/public/shop.html`: 북적북적 도서 쇼핑몰 화면과 이미지/표지
- `vue/public/shop.js`, `shop.css`: 쇼핑몰 Vue 화면과 스타일

## 실행 준비

1. PostgreSQL에서 사용할 데이터베이스를 준비합니다. 기본값은 `business`입니다.
2. 이 폴더의 `.env.example`을 `.env`로 복사한 뒤 DB 설정을 맞추고, `SESSION_SECRET`을 길고 무작위인 값으로 변경합니다.
3. FastAPI를 실행합니다.

```powershell
cd bookbook
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload
```

4. 새 터미널에서 Vue 앱을 실행합니다.

```powershell
cd bookbook\vue
npm install
npm run dev
```

앱은 `http://localhost:5173`에서 확인합니다. 쇼핑몰은 `http://localhost:5173/shop.html`에서 열립니다. Vue 앱의 회원 인증 API는 Vite 프록시를 통해 FastAPI의 `http://127.0.0.1:8000`으로 연결됩니다.

## 저장 후 바로 반영

`npm run dev`를 실행한 터미널을 켜 둔 채 `http://localhost:5173` 또는 `http://localhost:5173/shop.html`을 열어 작업합니다. `src/`의 Vue와 CSS 변경은 Vite가 즉시 반영하고, `public/`의 쇼핑몰 파일은 저장할 때 페이지를 자동 새로고침합니다. `vite.config.js`를 수정한 경우에는 개발 서버를 한 번 재시작하세요.

## API와 데모 범위

로그인, 회원가입, 세션 복원, 마이페이지, 관리자 회원 관리는 FastAPI API에 연결되어 있습니다. 쇼핑몰의 도서 목록, 장바구니, 찜, 도서 등록 데이터는 현재 브라우저 예시 데이터로 동작합니다. 기존 FastAPI에는 도서 API가 없으므로 쇼핑몰 데이터는 서버에 저장되지 않습니다.

관리자 화면은 일반 회원으로 가입한 다음 DB에서 해당 계정의 `role`을 `admin`으로 변경해야 사용할 수 있습니다. 도서 쇼핑몰의 상품 관리 화면은 디자인 확인용 프로토타입입니다.
