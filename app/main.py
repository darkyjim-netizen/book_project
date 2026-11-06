# app/main.py

import os

from dotenv import load_dotenv
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.database import Base, engine
from app import models
from app.routers import admin, auth, members

load_dotenv()

app = FastAPI(
    title="FastAPI 회원 관리 시스템",
    description="회원 CRUD, 세션 로그인, 관리자 권한 실습",
    version="1.0.0",
)

session_secret = os.getenv("SESSION_SECRET")

if not session_secret or session_secret == "replace-with-a-long-random-secret":
    raise RuntimeError(
        "실제 무작위 SESSION_SECRET 값을 .env에 설정하세요."
    )

https_only = (
    os.getenv("SESSION_HTTPS_ONLY", "false").lower() == "true"
)

app.add_middleware(
    SessionMiddleware,
    secret_key=session_secret,
    session_cookie="fastapi_session",
    same_site="lax",
    https_only=https_only,
    max_age=60 * 60 * 8,
)

# 학습용: 테이블이 없는 경우 생성합니다.
# 운영 환경에서는 Alembic 마이그레이션을 권장합니다.
Base.metadata.create_all(bind=engine)

app.include_router(auth.router)
app.include_router(members.router)
app.include_router(admin.router)


@app.get("/", tags=["기본"])
def home():
    return {
        "message": "FastAPI 회원 관리 시스템",
        "docs": "/docs",
    }


@app.get("/health", tags=["기본"])
def health():
    return {"status": "ok"}