# app/database.py

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()  # .env 파일에서 환경 변수를 불러옵니다.

# 데이터베이스 연결 정보를 딕셔너리로 정의합니다.
DATABASE_URL = {
    "drivername": "postgresql+psycopg2",  # 사용할 DB 드라이버 지정
    "username": os.getenv("DB_USER", "postgres"),  # DB 사용자 이름
    "password": os.getenv("DB_PASSWORD", ""),  # DB 비밀번호
    "host": os.getenv("DB_HOST", "localhost"),  # DB 서버 호스트 주소
    "port": int(os.getenv("DB_PORT", "5432")),  # DB 포트 번호
    "database": os.getenv("DB_NAME", "business"),  # 접속할 데이터베이스 이름
}

from sqlalchemy.engine import URL

database_url = URL.create(**DATABASE_URL)  # 딕셔너리 설정을 SQLAlchemy URL 객체로 변환합니다.

# 데이터베이스와 연결을 맺고 쿼리를 실행할 엔진을 생성합니다.
engine = create_engine(database_url, pool_pre_ping=True, echo=False)

# 데이터베이스 세션을 생성하는 팩토리(Factory)를 설정합니다.
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


# ORM 모델들이 상속받을 공통 기본 클래스(Base)를 정의합니다.
class Base(DeclarativeBase):
    pass


# 요청(Request)마다 독립된 DB 세션을 생성하고 안전하게 닫아주는 의존성 함수입니다.
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()