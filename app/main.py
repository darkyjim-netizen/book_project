# app/main.py

import os

from dotenv import load_dotenv
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app import models
from app.database import Base, engine
from app.routers import admin, auth, members

load_dotenv()  # .env 파일에서 환경 변수를 로드합니다.

# FastAPI 애플리케이션 인스턴스를 생성하고 기본 메타데이터를 설정합니다.
app = FastAPI(
    title="FastAPI 회원 관리 시스템",
    description="회원 CRUD, 세션 로그인, 관리자 권한 실습",
    version="1.0.0",
)

session_secret = os.getenv("SESSION_SECRET")

# 보안을 위해 세션 암호화 키가 안전하게 설정되었는지 확인하고, 미설정 시 실행을 중단합니다.
if not session_secret or session_secret == "replace-with-a-long-random-secret":
    raise RuntimeError(
        "실제 무작위 SESSION_SECRET 값을 .env에 설정하세요."
    )

https_only = (
    os.getenv("SESSION_HTTPS_ONLY", "false").lower() == "true"
)

# 서버 세션 관리를 위해 애플리케이션에 SessionMiddleware를 등록합니다.
app.add_middleware(
    SessionMiddleware,
    secret_key=session_secret,
    session_cookie="fastapi_session",
    same_site="lax",
    https_only=https_only,
    max_age=60 * 60 * 8,
)

# 학습용 편의를 위해 정의된 모델을 바탕으로 데이터베이스 테이블을 자동 생성합니다.
Base.metadata.create_all(bind=engine)

# 각 도메인별 라우터(인증, 회원, 관리자)를 애플리케이션에 등록합니다.
app.include_router(auth.router)
app.include_router(members.router)
app.include_router(admin.router)


# 서버의 기본 안내 메시지와 문서 링크를 반환하는 루트 엔드포인트입니다.
@app.get("/", tags=["기본"])
def home():
    return {
        "message": "FastAPI 회원 관리 시스템",
        "docs": "/docs",
    }


# 서버가 정상적으로 동작 중인지 확인하는 헬스 체크 엔드포인트입니다.
@app.get("/health", tags=["기본"])
def health():
    return {"status": "ok"}