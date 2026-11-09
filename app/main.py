# app/main.py

import os

from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from app.core.api_errors import http_error, validation_error

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import cors_origins
from starlette.middleware.sessions import SessionMiddleware

from app.auth import auth_router, session_router
from app.database import Base, engine
from app.models.category_model import Category
from app.routers import (
    admin_dashboard_router, admin_members_router, ai_router, cart_router,
    orders_router, products_router, profile_router,
)

load_dotenv()  # .env 파일에서 환경 변수를 로드합니다.

# FastAPI 애플리케이션 인스턴스를 생성하고 기본 메타데이터를 설정합니다.
app = FastAPI(
    title="FastAPI 회원 관리 시스템",
    description="회원 CRUD, 세션 로그인, 관리자 권한 실습",
    version="1.0.0",
)

# 환경 변수에 등록된 출처가 있을 때만 교차 출처 요청을 허용합니다.
origins = cors_origins()
if origins:
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])

# 세션 쿠키 서명에 사용할 비밀 키를 환경 변수에서 읽습니다.
session_secret = os.getenv("SESSION_SECRET")

# 보안을 위해 세션 암호화 키가 안전하게 설정되었는지 확인하고, 미설정 시 실행을 중단합니다.
if not session_secret or session_secret == "replace-with-a-long-random-secret":
    raise RuntimeError(
        "실제 무작위 SESSION_SECRET 값을 .env에 설정하세요."
    )

# 설정값에 따라 HTTPS 연결에서만 세션 쿠키를 전송하도록 지정합니다.
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
app.add_exception_handler(HTTPException, http_error)
app.add_exception_handler(RequestValidationError, validation_error)

# 각 모듈의 라우터를 순회하여 API 경로를 앱에 연결합니다.
for module in (
    session_router, profile_router, admin_members_router, auth_router, products_router,
    cart_router, orders_router, ai_router, admin_dashboard_router,
):
    app.include_router(module.router)


# 기존 문서 생성 함수를 보관하여 사용자 정의 함수에서 재사용합니다.
default_openapi = app.openapi


# API 문서의 입력 검증 오류 응답 코드를 실제 처리 방식인 400으로 맞춥니다.
def api_openapi():
    schema = default_openapi()
    for path, methods in schema["paths"].items():
        if path.startswith("/api/"):
            for operation in methods.values():
                responses = operation["responses"]
                if responses.pop("422", None):
                    responses.setdefault("400", {"description": "INVALID_INPUT_VALUE"})
    return schema


# 사용자 정의 함수가 API 문서를 생성하도록 연결합니다.
app.openapi = api_openapi


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
