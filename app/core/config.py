import os


# 환경 변수에서 허용할 출처 목록을 읽고 빈 값과 와일드카드를 제외합니다.
def cors_origins() -> list[str]:
    return [origin.strip() for origin in os.getenv("CORS_ORIGINS", "").split(",")
            if origin.strip() and origin.strip() != "*"]
