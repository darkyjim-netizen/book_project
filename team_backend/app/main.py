"""BookStore AI Commerce Platform - FastAPI 애플리케이션의 시작 파일.

개발 실행 명령
uvicorn team_backend.app.main:app --reload --host 0.0.0.0 --port 8000

운영 실행 명령
gunicorn team_backend.app.main:app -k uvicorn.workers.UvicornWorker -w 4 -b 0.0.0.0:8000

team_backend.app.main:app은 app/main.py 파일 안에 있는 app 객체를 뜻한다.
--reload는 개발 중 코드가 바뀌면 서버를 자동으로 다시 시작한다.
-w 4는 서버 작업 프로세스를 4개 실행한다.
"""

import os  # 폴더를 만들 때 사용한다.
import time  # 요청 처리 시간을 잴 때 사용한다.
from contextlib import asynccontextmanager  # 앱 시작과 종료 작업을 묶는 도구

from fastapi import FastAPI, Request                # FastAPI 앱과 HTTP 요청 정보를 가져온다.
from fastapi.middleware.cors import CORSMiddleware  # 허용된 웹사이트에서 API를 호출하게 한다.
from fastapi.middleware.gzip import GZipMiddleware  # 응답 데이터를 압축해 전송한다.
from fastapi.staticfiles import StaticFiles         # 이미지 같은 정적 파일을 웹에서 제공한다.

from team_backend.app.core.config import settings                # 설정 파일에서 앱 이름, DB 주소 등을 읽는다.
from team_backend.app.core.database import check_connection      # 데이터베이스 연결 상태를 확인한다.
from team_backend.app.core.exceptions import register_exception_handlers  # 공통 오류 처리기를 등록한다.
from team_backend.app.core.logging_config import setup_logging  # 로그 설정을 준비한다.
from team_backend.app.routers import register_routers            # 각 기능의 API 경로를 앱에 등록한다.

logger = setup_logging()  # 이 파일에서 사용할 로거를 만든다.


@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버가 시작될 때와 종료될 때 실행할 작업을 정의한다.

    yield 앞부분은 서버 시작 시, yield 다음 부분은 서버 종료 시 실행된다.
    """
    logger.info("=" * 70)
    logger.info(
        "%s v%s (%s) 기동",
        settings.APP_NAME,
        settings.APP_VERSION,
        settings.APP_ENV,
    )

    # 서버가 시작될 때 데이터베이스에 연결할 수 있는지 확인한다.
    db_ok = check_connection()
    if db_ok:
        logger.info(
            "데이터베이스 연결 확인: %s:%s/%s",
            settings.DB_HOST,
            settings.DB_PORT,
            settings.DB_NAME,
        )
    else:
        # DB 연결이 안 되어도 앱을 바로 종료하지 않고 오류 로그를 남긴다.
        logger.error("데이터베이스 연결 실패. 접속 정보와 PostgreSQL 상태를 확인하세요.")

    # 업로드 파일과 AI 모델 파일을 저장할 폴더가 없으면 만든다.
    # exist_ok=True는 폴더가 이미 있어도 오류를 내지 않게 한다.
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.AI_MODEL_DIR, exist_ok=True)

    if db_ok:
        # DB가 연결된 경우에만 추천 모델을 미리 불러와 첫 요청 지연을 줄인다.
        try:
            from team_backend.app.core.database import SessionLocal
            from team_backend.app.ai.recommender import get_recommender

            db = SessionLocal()
            try:
                recommender = get_recommender(db)
                logger.info(
                    "추천 모델 준비 완료: 사용자 %d, 도서 %d",
                    recommender.matrix.user_count,
                    recommender.matrix.item_count,
                )
            finally:
                db.close()
        except Exception as exc:  # pragma: no cover
            logger.warning("추천 모델 사전 로드 생략: %s", exc)
    else:
        logger.info("DB 연결 전까지 추천 모델 사전 로드를 건너뜁니다.")

    logger.info("API 문서: http://localhost:8000/docs")
    logger.info("=" * 70)

    yield  # 이 지점부터 서버가 요청을 처리한다.

    # 서버가 종료될 때 실행되는 코드다.
    logger.info("%s 종료", settings.APP_NAME)


# -----------------------------------------------------------------------------
# 애플리케이션 생성
# -----------------------------------------------------------------------------
app = FastAPI(
    title=settings.APP_NAME,  # API 문서에 표시할 서비스 이름
    version=settings.APP_VERSION,  # API 버전
    description="""
국내외 도서 쇼핑몰 플랫폼 API.

### 주요 기능
* **회원** : 가입/로그인(JWT), 등급·포인트·쿠폰, 배송지 관리
* **도서** : 카테고리/검색/정렬, 상세, 재고 관리
* **주문** : 장바구니, 주문, 결제(PG 연동), 배송 추적, 취소/환불
* **리뷰** : 작성/수정/도움됨, 감성 분석 결과 제공
* **고객지원** : 공지사항, 묻고답하기, FAQ, 1:1 채팅 상담(WebSocket)
* **AI** : 협업 필터링 추천, 리뷰 감성 분석, 매출 분석/판매 예측,
  RFM 세분화, 구매 분석, 고객 이탈 예측
* **관리자** : 대시보드, 상품/주문/회원/리뷰 관리, AI 모델 학습
""",
    docs_url="/docs",  # Swagger API 문서 주소
    redoc_url="/redoc",  # ReDoc API 문서 주소
    openapi_url="/openapi.json",  # API 설명 데이터 주소
    lifespan=lifespan,  # 서버 시작·종료 작업을 연결한다.
)

# -----------------------------------------------------------------------------
# 미들웨어
# 미들웨어는 요청이 API에 도착하거나 응답이 사용자에게 가는 중간에 실행된다.
# -----------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,  # 브라우저 요청을 허용할 웹사이트 목록
    allow_credentials=True,  # 쿠키나 인증 정보를 포함한 요청 허용
    allow_methods=["*"],  # GET, POST 등 모든 HTTP 메서드 허용
    allow_headers=["*"],  # 모든 요청 헤더 허용
    expose_headers=["X-Process-Time"],  # 브라우저 코드에서 이 응답 헤더를 읽을 수 있게 한다.
)

# 크기가 1,000바이트 이상인 응답은 gzip으로 압축한다.
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """응답에 처리 시간을 넣고, 오래 걸린 요청은 로그에 기록한다."""
    started = time.perf_counter()  # 요청 처리 시작 시각을 고정밀도로 기록한다.

    response = await call_next(request)  # 다음 미들웨어와 API 함수를 실행한다.

    elapsed = time.perf_counter() - started  # 시작부터 응답 생성까지 걸린 시간(초)
    response.headers["X-Process-Time"] = f"{elapsed:.4f}"  # 응답 헤더에 초 단위로 추가한다.

    # 1초보다 오래 걸린 요청만 경고 로그로 남긴다.
    if elapsed > 1.0:
        logger.warning(
            "느린 요청: %s %s (%.3fs)",
            request.method,
            request.url.path,
            elapsed,
        )

    return response  # 처리한 응답을 사용자에게 돌려준다.


# -----------------------------------------------------------------------------
# 예외 처리 / 정적 파일 / API 경로 등록
# -----------------------------------------------------------------------------
register_exception_handlers(app)  # 앱에서 발생한 오류를 공통 규칙으로 처리한다.

# app/static 폴더의 파일을 /static/... 주소로 제공한다.
# 예: app/static/logo.png 파일은 /static/logo.png 주소로 접근한다.
static_dir = os.path.join(os.path.dirname(__file__), "static")
# StaticFiles는 앱을 불러올 때 폴더가 있는지 확인한다.
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

register_routers(app)  # 회원, 도서, 주문 등 각 기능의 API 경로를 등록한다.


# -----------------------------------------------------------------------------
# 헬스 체크
# 서버와 데이터베이스가 동작하는지 확인하는 API다.
# -----------------------------------------------------------------------------
@app.get("/health", tags=["시스템"], summary="헬스 체크")
def health():
    """애플리케이션과 데이터베이스의 현재 상태를 반환한다."""
    db_ok = check_connection()  # DB에 연결할 수 있으면 True, 아니면 False

    return {
        # DB 연결이 되면 정상, 안 되면 일부 기능에 문제가 있을 수 있는 상태로 표시한다.
        "status": "ok" if db_ok else "degraded",
        "app": settings.APP_NAME,  # 앱 이름
        "version": settings.APP_VERSION,  # 앱 버전
        "environment": settings.APP_ENV,  # 개발 또는 운영 환경
        "database": "connected" if db_ok else "disconnected",  # DB 연결 상태
    }


@app.get("/api/v1/health", tags=["시스템"], summary="헬스 체크(API)")
def api_health():
    """API 경로 규칙에 맞춘 헬스 체크 주소다."""
    # 위의 health()와 같은 결과를 돌려준다.
    return health()


# 이 파일을 직접 실행했을 때만 아래 코드를 실행한다.
# 다른 파일에서 import team_backend.app.main을 하면 서버가 자동 실행되지 않는다.
if __name__ == "__main__":  # pragma: no cover
    import uvicorn  # 개발 서버를 실행하는 프로그램

    uvicorn.run(
        "team_backend.app.main:app",  # 실행할 FastAPI 앱의 위치
        host="0.0.0.0",  # 컴퓨터의 네트워크 인터페이스에서 요청을 받는다.
        port=8000,  # 서버 포트 번호
        reload=settings.DEBUG,  # DEBUG가 True면 코드 변경 시 자동 재시작
        log_level=settings.LOG_LEVEL.lower(),  # 로그 단계. 예: info, debug
    )
