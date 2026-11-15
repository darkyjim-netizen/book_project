# FastAPI Step 06 - Vue 3 Member Management Frontend

첨부된 6단계 교안의 FastAPI 세션 인증·인가 API와 연동하는 Vue 프런트엔드입니다.

## 1. 기술 스택

- Vue 3 + Vite + JavaScript
- Vue Router 4
- Pinia 3
- Axios
- Tailwind CSS 3

## 2. 실행 환경

- Node.js 20 이상 권장
- FastAPI: `http://127.0.0.1:8000`
- Vue: `http://localhost:5173`
- PostgreSQL: FastAPI 백엔드에서 연결

## 3. 설치 및 실행

```powershell
cd bookbook\vue
npm install
npm run dev
```

브라우저: `http://localhost:5173`

프로덕션 빌드:

```powershell
npm run build
npm run preview
```

## 4. FastAPI 백엔드 실행

첨부 교안의 백엔드 프로젝트 루트에서 가상환경을 활성화하고 패키지를 설치한 뒤 실행합니다.

```powershell
pip install -r requirements.txt
uvicorn main:app --reload
```

Swagger: `http://127.0.0.1:8000/docs`

## 5. 화면 URL

| URL | 설명 | 권한 |
|---|---|---|
| `/login` | 로그인 | 비로그인 |
| `/register` | 회원가입 | 비로그인 |
| `/dashboard` | 대시보드 | 로그인 |
| `/profile` | 내 정보 조회/수정/탈퇴 | 로그인 |
| `/admin/members` | 회원 목록 | 관리자 |
| `/admin/members/:id` | 회원 상세/권한/상태/삭제 | 관리자 |

## 6. 백엔드 API 연결

| HTTP | URL | 프런트엔드 |
|---|---|---|
| POST | `/auth/register` | 회원가입 |
| POST | `/auth/login` | 로그인 |
| POST | `/auth/logout` | 로그아웃 |
| GET | `/auth/me` | 새로고침 시 로그인 복원 |
| GET | `/members/me` | 내 정보 |
| PATCH | `/members/me` | 내 정보 수정 |
| DELETE | `/members/me` | 회원 탈퇴 |
| GET | `/admin/members?page=1&size=20` | 관리자 회원 목록 |
| GET | `/admin/members/{id}` | 관리자 회원 상세 |
| PATCH | `/admin/members/{id}` | 권한/활성 상태 변경 |
| DELETE | `/admin/members/{id}` | 관리자 회원 삭제 |

## 7. 세션 쿠키 처리

`src/api/http.js`에서 `withCredentials: true`를 설정합니다. FastAPI SessionMiddleware가 발급하는 세션 쿠키를 브라우저가 요청에 포함하도록 하기 위한 설정입니다.

개발 환경에서는 Vite proxy를 사용합니다. `vite.config.js`의 `/auth`, `/members`, `/admin`, `/health` 요청을 FastAPI 8000 포트로 전달합니다. 같은 출처의 개발 프록시를 통하므로 일반적인 개발 실행에서는 브라우저 CORS 설정이 개입하지 않습니다.

프록시 없이 다른 출처의 API를 직접 호출하는 경우 FastAPI에 다음과 같은 CORS 설정을 추가해야 합니다.

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)
```

`allow_credentials=True`일 때 `allow_origins=["*"]`를 사용하지 마세요. 운영 환경에서는 실제 프런트엔드 origin만 허용하세요.

## 8. 인증 상태 처리

- Pinia는 사용자 표시 정보와 로그인 상태를 메모리에 보관합니다.
- 새로고침하면 Vue Router 가드가 `/auth/me`를 호출합니다.
- 브라우저가 세션 쿠키를 전송하고, FastAPI가 세션을 확인합니다.
- 비로그인 사용자는 보호된 페이지 대신 로그인 화면으로 이동합니다.
- 일반 회원은 관리자 화면에 접근할 수 없습니다.
- 백엔드의 `require_admin` 검사가 최종 권한 판단을 담당합니다.

프런트엔드의 라우터 가드는 UX를 위한 보조 장치입니다. 보안 경계는 반드시 백엔드에서 유지해야 합니다.

## 9. 회원가입 요청 필드

```json
{
  "username": "user01",
  "email": "user01@example.com",
  "password": "ChangeMe123!",
  "display_name": "홍길동"
}
```

`role`, `is_active`는 프런트엔드에서 보내지 않습니다. 백엔드가 `role=member`, `is_active=true`를 지정해야 합니다.

## 10. 관리자 계정 생성

교안대로 일반 회원으로 가입한 후 PostgreSQL에서 최초 관리자 권한을 부여합니다.

```sql
UPDATE members
SET role = 'admin'
WHERE username = 'admin01';
```

그 계정으로 다시 로그인하거나 새로고침하면 `/auth/me`에서 관리자 권한을 확인합니다.

## 11. 백엔드 CORS 및 세션 보안 주의

1. 개발 proxy 사용 시 프런트엔드 API 주소는 상대경로(`/auth/login`)로 유지합니다.
2. 직접 교차 출처 호출 시 CORS `allow_credentials=True`와 정확한 origin이 필요합니다.
3. 운영 HTTPS에서는 `SESSION_HTTPS_ONLY=true`를 설정합니다.
4. 세션 쿠키는 인증 수단입니다. 비밀번호나 비밀번호 해시를 프런트엔드 저장소에 보관하지 않습니다.
5. Starlette SessionMiddleware 쿠키는 서명되지만 암호화되지는 않습니다. 세션에는 `member_id` 이외의 민감정보를 넣지 않습니다.
6. 쿠키 기반 인증은 CSRF 위협을 고려해야 합니다. 운영 배포 전 CSRF 토큰 검증, Origin 검증, SameSite 정책을 설계하고 상태 변경 요청에 적용하세요.
7. 비밀번호 변경 기능은 첨부 교안 API에 없으므로 이 프런트엔드에도 임의로 추가하지 않았습니다.

## 12. 교안 API 응답 계약

프런트엔드는 교안의 Pydantic 스키마를 기준으로 합니다.

Member 응답:
`id`, `username`, `email`, `display_name`, `role`, `is_active`, `created_at`, `updated_at`

로그인 응답:
`message`, `member`

관리자 목록 응답:
`items`, `total`, `page`, `size`

백엔드가 이 필드명과 응답 구조를 유지해야 프런트엔드 코드 수정 없이 연동할 수 있습니다.

## 13. 주의사항

- 이메일/아이디 중복 확인은 별도 검사 API가 교안에 없으므로 가입 요청 시 서버 응답(409)을 표시합니다.
- 현재 관리자 목록은 교안의 목록 API가 제공하는 페이지 단위 데이터를 표시합니다.
- 회원 삭제는 교안 API의 물리 삭제 동작을 그대로 호출합니다.
- 회원 탈퇴 및 관리자 삭제는 되돌릴 수 없으므로 확인창을 표시합니다.
