# app/models.py

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


# 회원(Member) 정보를 저장하기 위한 SQLAlchemy ORM 모델 클래스입니다.
class Member(Base):
    __tablename__ = "members"  # 데이터베이스에 생성될 테이블 이름을 지정합니다.

    # role 컬럼에 'member' 또는 'admin' 값만 허용하도록 제약 조건을 설정합니다.
    __table_args__ = (
        CheckConstraint(
            "role IN ('member', 'admin')",
            name="ck_members_role",
        ),
    )

    # 기본키(Primary Key)이자 인덱스가 적용되는 고유 회원 ID입니다.
    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    # 로그인에 사용되는 중복 불가 회원 아이디입니다.
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )

    # 연락 및 식별용 중복 불가 이메일 주소입니다.
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )

    # 안전하게 암호화된 비밀번호 해시값을 저장합니다.
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # 화면에 표시될 사용자의 닉네임 또는 이름입니다.
    display_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # 사용자의 권한을 구분하며 기본값으로 'member'를 가집니다.
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="member",
        server_default="member",
    )

    # 계정 활성화 여부를 나타내며 기본값은 활성(True) 상태입니다.
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    # 레코드가 처음 생성된 시각을 자동으로 기록합니다.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # 레코드가 수정될 때마다 시각을 자동으로 갱신합니다.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )