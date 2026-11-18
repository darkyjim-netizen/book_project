"""데이터베이스 연결과 ORM 모델의 공통 기반을 설정한다.

동기 방식으로 DB에 연결하며, FastAPI의 Depends(get_db)를 통해
API 함수에 DB 세션을 전달할 수 있다.
"""
from typing import Generator  # yield로 세션을 전달하는 함수의 반환 타입 표시

from sqlalchemy import create_engine, event, text  # DB 엔진 생성 및 연결 이벤트 등록
from sqlalchemy.engine import URL   # DB 접속 주소를 안전하게 만들고 다루는 SQLAlchemy 기능 가져옴.
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker  # ORM 모델과 DB 세션 기능
from sqlalchemy.pool import QueuePool  # DB 연결을 만들어 두고 재사용하는 연결 풀

from app.core.config import settings  # .env 등에서 읽은 DB 접속 설정

# -----------------------------------------------------------------------------
# URL.create()를 사용하면 비밀번호에 @, :, / 같은 문자가 포함되어도
# DB 접속 주소를 안전하게 만들 수 있다.
# -----------------------------------------------------------------------------
database_url = URL.create(
    drivername="postgresql+psycopg2",
    username=settings.DB_USER,
    password=settings.DB_PASSWORD,
    host=settings.DB_HOST,
    port=settings.DB_PORT,
    database=settings.DB_NAME,
)


# -----------------------------------------------------------------------------
# DB 엔진
# 엔진은 DB에 연결하는 방법과 연결 재사용 규칙을 관리한다.
# -----------------------------------------------------------------------------
engine = create_engine(
    settings.database_url,  # DB 주소, 사용자명, 비밀번호 등이 들어 있는 접속 주소
    poolclass=QueuePool,  # 연결을 풀에 보관해 다음 요청에서 재사용한다.
    pool_size=settings.DB_POOL_SIZE,  # 기본으로 유지할 DB 연결 수
    max_overflow=settings.DB_MAX_OVERFLOW,  # 요청이 몰릴 때 추가로 열 수 있는 연결 수
    pool_pre_ping=True,  # 재사용 전 연결이 살아 있는지 확인한다.
    pool_recycle=1800,  # 연결을 만든 지 1,800초가 지나면 새 연결로 교체한다.
    echo=settings.DB_ECHO,  # True면 실행한 SQL을 로그에 출력한다.
    future=True,  # SQLAlchemy의 최신 방식에 맞춰 동작하게 한다.
)


# 새 DB 연결이 실제로 만들어질 때 실행할 함수를 등록한다.
@event.listens_for(engine, "connect")
def _set_search_path(dbapi_connection, connection_record):  # noqa: ANN001
    """DB 연결마다 기본 스키마와 시간대를 설정한다."""

    # SQL 명령을 DB에 보내기 위한 커서를 만든다.
    cursor = dbapi_connection.cursor()
    try:
        # 테이블 이름에 스키마를 매번 적지 않아도 찾을 순서를 지정한다.
        # 예를 들어 SELECT * FROM books는 shop.books를 우선 찾는다.
        cursor.execute("SET search_path TO shop, ai, log, public")

        # DB에서 날짜와 시간을 다룰 때 한국 시간대를 사용한다.
        cursor.execute("SET timezone TO 'Asia/Seoul'")
    finally:
        # SQL 실행 중 문제가 생겨도 커서는 닫는다.
        cursor.close()


# API 요청에서 사용할 DB 세션을 만드는 설정이다.
SessionLocal = sessionmaker(
    bind=engine,  # 위에서 만든 엔진으로 DB에 연결한다.
    autoflush=False,  # ORM 변경 내용을 쿼리 전에 자동으로 DB에 보내지 않는다.
    autocommit=False,  # DB 변경을 자동 확정하지 않는다. 필요한 곳에서 commit()해야 한다.
    expire_on_commit=False,  # commit 후에도 이미 읽은 객체의 값을 계속 사용할 수 있게 한다.
    class_=Session,  # SQLAlchemy의 동기 Session 클래스를 사용한다.
)


class Base(DeclarativeBase):
    """DB 테이블과 연결되는 ORM 모델들이 상속할 공통 클래스."""

    pass  # 공통 동작을 추가하지 않고 기본 기능을 그대로 사용한다.


# -----------------------------------------------------------------------------
# DB 세션 의존성
# FastAPI에서 Depends(get_db)로 사용하면 요청 처리 동안 세션을 제공한다.
# -----------------------------------------------------------------------------
def get_db() -> Generator[Session, None, None]:
    """DB 세션을 열어 API 함수에 전달하고, 요청이 끝나면 정리한다."""

    db = SessionLocal()  # 새 DB 세션을 만든다.
    try:
        yield db  # yield 아래 정리 코드는 요청 처리가 끝난 뒤 실행된다.
    except Exception:
        # DB 작업 중 오류가 나면 아직 확정되지 않은 변경을 취소한다.
        db.rollback()
        raise  # 오류를 다시 발생시켜 FastAPI가 처리하게 한다.
    finally:
        # 성공하거나 실패해도 세션을 닫는다.
        # 연결은 연결 풀로 돌아가 재사용될 수 있다.
        db.close()


def check_connection() -> bool:
    """DB에 연결할 수 있으면 True, 연결에 실패하면 False를 돌려준다."""

    # SQL 문장을 표현하는 데 필요한 도구를 함수 안에서 불러온다.
    from sqlalchemy import text

    try:
        # DB 연결을 열고 간단한 확인용 SQL을 실행한다.
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        return True  # 연결과 쿼리가 성공하면 True
    except Exception:  # pragma: no cover
        # 연결이나 쿼리에 오류가 나면 False
        return False