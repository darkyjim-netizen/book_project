
from contextlib import asynccontextmanager

from fastapi import FastAPI

from fastapi.staticfiles import StaticFiles

from app.core.config import settings

from app.core.database import Base, engine

from app.models.review import Review

from app.services.sentiment_service import (
    get_sentiment_analyzer
)

from app.controllers.web_controller import router as web_router

from app.controllers.api_controller import router as api_router


@asynccontextmanager
async def lifespan(app: FastAPI):

    print("===================================")

    print("한국어 리뷰 감정 분석 시스템 시작")

    # 데이터베이스 테이블 생성
    Base.metadata.create_all(bind=engine)

    # 애플리케이션 시작 시 모델 로딩
    get_sentiment_analyzer()

    print("데이터베이스 초기화 완료")
    print("AI 모델 초기화 완료")

    yield

    print("한국어 리뷰 감정 분석 시스템 종료")


app = FastAPI(
    title=settings.APP_NAME,
    description="Hugging Face 기반 한국어 리뷰 감정 분석 API",
    version="1.0.0",
    lifespan=lifespan
)


# 정적 파일 연결
app.mount(
    "/static",
    StaticFiles(directory="app/static"),
    name="static"
)


# 웹 Controller
app.include_router(web_router)


# API Controller
app.include_router(api_router)


@app.get("/health")
def health():

    return {
        "status": "OK",
        "message": "한국어 감정 분석 시스템 정상 작동"
    }