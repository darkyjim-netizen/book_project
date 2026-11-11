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
