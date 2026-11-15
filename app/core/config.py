"""쇼핑몰 백엔드에서 사용하는 설정을 한곳에 모아둔다.

이 코드에서 Settings()를 만들면 OS 환경 변수 → .env 파일 → 코드의 기본값
순서로 값을 찾는다. pydantic-settings는 읽은 값을 지정한 타입으로 변환하고 검사한다.
"""

from functools import lru_cache     # 한 번 만든 설정 객체를 재사용할 때 사용
from typing import List             # 리스트에 어떤 타입의 값이 들어가는지 표시

from pydantic import field_validator  # 특정 설정값을 검사하기 전에 가공하는 데 사용
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # BaseSettings를 상속하면 환경 변수나 .env 파일에서 설정값을 읽을 수 있다.
    model_config = SettingsConfigDict(
        env_file=".env",             # 앱을 실행한 작업 폴더에서 .env 파일을 찾는다.
        env_file_encoding="utf-8",   # .env 파일을 UTF-8로 읽는다.
        case_sensitive=False,       # 환경 변수 이름의 대소문자를 구분하지 않는다.
        extra="ignore",             # .env에 이 클래스에 없는 항목이 있어도 무시한다.
    )

    # ------------------------------------------------------------------ 기본
    APP_NAME: str = "BookBook AI Commerce"  # 애플리케이션 이름
    APP_VERSION: str = "1.0.0"             # 애플리케이션 버전
    APP_ENV: str = "development"           # 실행 환경. 예: development, production
    DEBUG: bool = True                     # 디버그 모드 사용 여부
    API_PREFIX: str = "/api/v1"             # API 주소 앞에 붙는 공통 경로
    TIMEZONE: str = "Asia/Seoul"             # 앱에서 시간 처리를 할 때 사용할 시간대

    # ------------------------------------------------------------- 데이터베이스
    DB_HOST: str = "localhost"       # PostgreSQL 서버 주소. localhost는 내 컴퓨터를 뜻한다.
    DB_PORT: int = 5432              # PostgreSQL에 접속할 때 쓰는 포트 번호
    DB_NAME: str = "book"        # 접속할 데이터베이스 이름
    DB_USER: str = "postgres"        # 데이터베이스 접속 계정
    DB_PASSWORD: str = "1004"        # 데이터베이스 접속 비밀번호의 기본값
    DB_SCHEMA: str = "shop"           # DB 안에서 상품·주문 등의 테이블을 묶는 이름
    DB_POOL_SIZE: int = 10           # 재사용할 수 있도록 유지하는 DB 연결 수
    DB_MAX_OVERFLOW: int = 20        # 요청이 몰릴 때 기본 연결 수를 넘어 추가로 열 수 있는 수
    DB_ECHO: bool = False            # SQLAlchemy가 실행하는 SQL을 로그에 표시할지 여부

    # ------------------------------------------------------------------ 보안
    # JWT에 서명할 때 쓰는 키. 운영 환경에서는 환경 변수로 별도 값을 설정한다.
    SECRET_KEY: str = "change-this-secret-key-in-production-env-file"
    ALGORITHM: str = "HS256"  # JWT 서명에 사용하는 알고리즘

    # 액세스 토큰은 로그인 후 API를 호출할 때 사용한다. 기본 유효 시간은 120분이다.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 2

    # 리프레시 토큰은 새 액세스 토큰을 발급받을 때 사용한다. 기본 유효 기간은 14일이다.
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 14

    PASSWORD_MIN_LENGTH: int = 8  # 가입이나 비밀번호 변경 시 적용할 최소 글자 수
    LOGIN_FAIL_LIMIT: int = 5     # 로그인 실패를 제한할 때 사용할 기준 횟수

    # ------------------------------------------------------------------ CORS
    # 브라우저에서 백엔드 API에 접근을 허용할 출처 목록.
    # 출처는 프로토콜(http), 호스트(localhost), 포트(5173)의 조합이다.
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://localhost:8000",
    ]

    # ------------------------------------------------------------ 파일 업로드
    UPLOAD_DIR: str = "app/static/upload"      # 업로드한 파일을 저장할 폴더
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024   # 파일 하나의 최대 용량. 바이트 단위로 계산한다.
    ALLOWED_IMAGE_EXT: List[str] = [".jpg", ".jpeg", ".png", ".gif", ".webp"]  # 허용할 이미지 확장자

    # -------------------------------------------------------------- 쇼핑 정책
    DEFAULT_SHIP_FEE: int = 3000   # 기본 배송비 3,000원
    FREE_SHIP_LIMIT: int = 20000   # 무료 배송을 적용하는 금액 기준 20,000원
    POINT_SAVE_RATE: float = 0.01  # 포인트 적립률 1%. 예: 10,000원 × 0.01 = 100포인트
    ORDER_CONFIRM_DAYS: int = 7    # 주문 확정에 적용할 기간
    CART_MAX_ITEMS: int = 100      # 장바구니에 담을 수 있는 항목 수의 상한

    # ------------------------------------------------------------------- PG
    # PG는 카드 결제 등 온라인 결제를 처리하는 결제대행사를 뜻한다.
    PG_PROVIDER: str = "INICIS"      # 이용할 결제대행사
    PG_MID: str = "INIpayTest"       # 결제대행사에서 사용하는 테스트 가맹점 ID
    PG_API_KEY: str = "test-api-key" # 결제 API를 호출할 때 사용하는 테스트 키
    PG_MOCK_MODE: bool = True        # 실제 결제 대신 모의 결제 처리를 사용할지 여부

    # ------------------------------------------------------------------- AI
    AI_MODEL_DIR: str = "app/ai/artifacts"  # 학습한 모델 파일을 저장하거나 불러올 폴더

    # CF는 협업 필터링을 뜻한다. 여러 사용자의 행동 패턴을 비교해 상품을 추천하는 방식이다.
    CF_MIN_INTERACTIONS: int = 2  # 추천에 사용할 최소 사용자 행동 기록 수
    CF_TOP_N: int = 20            # 추천 결과에 포함할 상품 수
    CF_NEIGHBOR_K: int = 40       # 추천 계산에 참고할 유사 대상의 수

    SENTIMENT_MODEL_VERSION: str = "kosa-lr-v1"  # 리뷰 감성 분석 모델의 버전 이름
    FORECAST_HORIZON_DAYS: int = 30              # 앞으로 며칠까지 예측할지 정하는 값
    CHURN_THRESHOLD_HIGH: float = 0.7            # 고객 이탈 위험을 높음으로 판단하는 점수 기준
    CHURN_THRESHOLD_MID: float = 0.4             # 고객 이탈 위험을 중간으로 판단하는 점수 기준
    CHURN_INACTIVE_DAYS: int = 90                 # 이탈 분석에 사용할 비활성 기간 기준

    # ----------------------------------------------------------------- 로깅
    LOG_LEVEL: str = "INFO"  # 로그를 어느 수준부터 남길지 정하는 값
    LOG_DIR: str = "logs"    # 로그 파일을 저장할 폴더

    # 두 설정값이 이 함수에 문자열로 들어오면 리스트로 바꾼다.
    # mode="before"는 Pydantic이 리스트 타입을 검사하기 전에 이 함수를 실행한다는 뜻이다.
    @field_validator("CORS_ORIGINS", "ALLOWED_IMAGE_EXT", mode="before")
    @classmethod
    def _split_csv(cls, v):
        if isinstance(v, str):
            # 예: ".jpg, .png, " → [".jpg", ".png"]
            # 쉼표로 나누고 각 항목의 앞뒤 공백과 빈 항목을 제거한다.
            return [item.strip() for item in v.split(",") if item.strip()]

        # 이미 리스트처럼 문자열이 아닌 값이면 그대로 넘겨서 타입 검사를 받는다.
        return v

    # ------------------------------------------------------------ 파생 속성
    # 파생 속성은 이미 읽어 둔 설정값을 조합하거나 계산해서 만든다.
    # @property를 붙이면 settings.database_url처럼 괄호 없이 값을 읽을 수 있다.
    @property
    def database_url(self) -> str:
        """DB 접속 정보를 조합해 동기 접속 주소를 만든다."""
        # 동기 방식은 DB 작업이 끝날 때까지 해당 코드가 기다린다.
        # 이 주소는 psycopg2 드라이버를 사용하는 SQLAlchemy에 전달한다.
        return (
            f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def async_database_url(self) -> str:
        """DB 접속 정보를 조합해 비동기 접속 주소를 만든다."""
        # 비동기 방식에서는 DB 응답을 기다리는 동안 다른 작업을 처리할 수 있다.
        # 이 주소를 실제로 사용하려면 asyncpg 드라이버가 필요하다.
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def is_production(self) -> bool:
        """현재 설정이 운영 환경이면 True를 반환한다."""
        # lower()로 소문자로 바꾸므로 "Production"이나 "PROD"도 True가 된다.
        return self.APP_ENV.lower() in ("production", "prod")


# get_settings()를 처음 호출할 때만 Settings() 객체를 만들고,
# 이후에는 같은 객체를 재사용해 설정 파일을 매번 다시 읽지 않는다.
@lru_cache
def get_settings() -> Settings:
    return Settings()


# 이 모듈을 처음 불러올 때 설정 객체를 만든다.
# 다른 코드에서 settings를 가져와 settings.DB_PORT처럼 접근할 수 있다.
settings = get_settings()


import os


# 환경 변수에서 허용할 출처 목록을 읽고 빈 값과 와일드카드를 제외합니다.
def cors_origins() -> list[str]:
    return [origin.strip() for origin in os.getenv("CORS_ORIGINS", "").split(",")
            if origin.strip() and origin.strip() != "*"]


# 프런트엔드와 백엔드의 기본 주소입니다. 결제 후 이동할 주소를 만들 때 사용합니다.
def frontend_url() -> str:
    return os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")


def backend_url() -> str:
    return os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")


# 토스페이먼츠 결제창을 여는 데 쓰는 공개 키입니다.
def toss_client_key() -> str:
    return os.getenv("TOSS_CLIENT_KEY", "")


# 토스페이먼츠 승인·취소 API를 호출할 때 쓰는 비밀 키입니다. 서버 밖으로 내보내지 않습니다.
def toss_secret_key() -> str:
    return os.getenv("TOSS_SECRET_KEY", "")


def toss_api_base_url() -> str:
    return os.getenv("TOSS_API_BASE_URL", "https://api.tosspayments.com").rstrip("/")


# 결제 성공·실패 시 토스페이먼츠가 사용자를 돌려보낼 주소입니다.
def payment_success_url() -> str:
    return os.getenv("PAYMENT_SUCCESS_URL") or f"{backend_url()}/api/payments/toss/success"


def payment_fail_url() -> str:
    return os.getenv("PAYMENT_FAIL_URL") or f"{backend_url()}/api/payments/toss/fail"
