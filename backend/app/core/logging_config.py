"""콘솔과 날짜별 로그 파일에 기록하도록 로깅을 설정한다."""

import logging  # 로그를 기록하고 관리하는 기본 기능
import logging.handlers  # 날짜 기준 로그 파일 분리 기능
import os  # 로그 폴더 경로를 만들 때 사용
import sys  # 콘솔 출력 위치를 지정할 때 사용

from app.core.config import settings  # 로그 폴더, 로그 수준, DB 설정을 읽는다.


# 로그 한 줄의 모양
# 예: 2026-11-15 13:00:00 | INFO    | bookstore | 서버 시작
LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"

# 로그에 표시할 날짜와 시간 모양
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging() -> logging.Logger:
    """루트 로거를 설정하고 bookstore 이름의 로거를 돌려준다."""

    # 로그 폴더가 없으면 만든다. 이미 있어도 오류가 나지 않는다.
    os.makedirs(settings.LOG_DIR, exist_ok=True)

    # 루트 로거는 별도로 설정하지 않은 대부분의 로거가 사용하는 기본 로거다.
    root = logging.getLogger()

    # 설정한 로그 수준 이상의 메시지만 기록한다.
    # 예를 들어 LOG_LEVEL이 INFO면 INFO, WARNING, ERROR 등을 기록한다.
    # 설정값이 올바르지 않으면 INFO를 기본값으로 사용한다.
    root.setLevel(
        getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    )

    # 루트 로거에 이미 연결된 출력 장치를 모두 제거한다.
    root.handlers.clear()

    # 위에서 지정한 형식과 날짜 형식을 로그 출력에 적용한다.
    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)

    # 로그를 콘솔에 출력하는 설정이다.
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    # 일반 로그를 app.log 파일에 저장한다.
    # 매일 자정에 새 파일로 나누고, 이전 로그 파일은 최대 30개 보관한다.
    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=os.path.join(settings.LOG_DIR, "app.log"),
        when="midnight",
        backupCount=30,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # 오류 로그는 error.log 파일에도 별도로 저장한다.
    # 날짜별로 파일을 나누고 이전 로그 파일은 최대 90개 보관한다.
    error_handler = logging.handlers.TimedRotatingFileHandler(
        filename=os.path.join(settings.LOG_DIR, "error.log"),
        when="midnight",
        backupCount=90,
        encoding="utf-8",
    )

    # ERROR와 CRITICAL 수준의 로그만 이 파일에 기록한다.
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root.addHandler(error_handler)

    # SQLAlchemy가 실행하는 SQL 로그 수준을 설정한다.
    # DB_ECHO가 True면 INFO부터, False면 WARNING부터 기록한다.
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.DB_ECHO else logging.WARNING
    )

    # Uvicorn의 웹 요청 로그를 INFO 수준으로 기록한다.
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)

    # 이름이 bookstore인 로거를 돌려준다.
    # 예: logger = setup_logging()
    #     logger.info("서버 시작")
    # 이 로그도 기본적으로 루트 로거의 콘솔과 파일 설정을 따른다.
    return logging.getLogger("bookstore")