"""회원 도메인의 데이터베이스 테이블을 파이썬 클래스로 정의한다."""
from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import (
    BigInteger,  # 큰 정수형
    Boolean,     # 참/거짓
    Date,        # 날짜
    DateTime,    # 날짜와 시각
    Enum as PgEnum,  # DB의 ENUM 타입
    ForeignKey,  # 다른 테이블의 키를 참조하는 제약 조건
    Integer,
    Numeric,     # 정밀한 숫자. 금액·비율 등에 사용
    SmallInteger,
    String,      # 최대 길이가 있는 문자열
    Text,        # 긴 문자열
    func,        # now() 같은 DB 함수를 표현할 때 사용
)
from sqlalchemy.dialects.postgresql import UUID  # PostgreSQL UUID 타입
from sqlalchemy.orm import Mapped, mapped_column, relationship

from team_backend.app.core.database import Base  # ORM 모델들이 상속하는 공통 클래스
from team_backend.app.models.enums import GenderType, MemberRole, MemberStatus, PointReason


class MemberGrade(Base):
    """회원 등급 정보를 저장하는 테이블."""

    __tablename__ = "member_grades"  # 실제 DB 테이블 이름
    __table_args__ = {"schema": "shop"}  # shop 스키마 안에 테이블을 만든다.

    grade_id: Mapped[int] = mapped_column(
        SmallInteger,
        primary_key=True,  # 등급을 구별하는 기본 키
    )
    grade_code: Mapped[str] = mapped_column(
        String(20),
        unique=True,       # 등급 코드가 중복될 수 없다.
        nullable=False,    # 반드시 값이 있어야 한다.
    )
    grade_name: Mapped[str] = mapped_column(String(50), nullable=False)  # 화면에 표시할 등급명
    min_amount: Mapped[float] = mapped_column(Numeric(12, 0), default=0)  # 등급 조건이 되는 최소 구매액
    discount_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=0)  # 할인율
    point_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=1.0)  # 포인트 적립률
    free_ship_limit: Mapped[float] = mapped_column(Numeric(12, 0), default=20000)  # 무료 배송 기준 금액
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=0)  # 등급 표시 순서

    # server_default는 파이썬이 아니라 DB가 기본값을 채운다는 뜻이다.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # 한 등급에 여러 회원이 속할 수 있다.
    # Member.grade와 양방향으로 연결된다.
    members: Mapped[List["Member"]] = relationship(back_populates="grade")


class Member(Base):
    """회원 기본 정보를 저장하는 테이블."""

    __tablename__ = "members"
    __table_args__ = {"schema": "shop"}

    member_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # 회원 번호
    uuid: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        server_default=func.gen_random_uuid(),
    )  # 외부 노출 등에 사용할 UUID. UUID를 DB가 자동 생성한다.

    email: Mapped[str] = mapped_column(
        String(190),
        unique=True,     # 같은 이메일로 여러 계정을 만들 수 없다.
        nullable=False,  # 이메일은 필수다.
        index=True,      # 이메일 검색을 빠르게 하기 위한 인덱스
    )
    password_hash: Mapped[Optional[str]] = mapped_column(String(255))  # 해시된 비밀번호. 소셜 가입 등은 없을 수 있다.
    name: Mapped[str] = mapped_column(String(60), nullable=False)  # 회원 이름
    nickname: Mapped[Optional[str]] = mapped_column(String(60))  # 선택 입력 별명
    phone: Mapped[Optional[str]] = mapped_column(String(20))  # 선택 입력 전화번호
    birth_date: Mapped[Optional[date]] = mapped_column(Date)  # 선택 입력 생년월일

    # PostgreSQL에 미리 정의한 ENUM 타입을 사용한다.
    # create_type=False는 이 모델이 ENUM 타입을 새로 만들지 않게 한다.
    gender: Mapped[GenderType] = mapped_column(
        PgEnum(GenderType, name="gender_type", schema="shop", create_type=False),
        default=GenderType.N,  # 값을 주지 않았을 때 미입력 상태로 설정
    )
    role: Mapped[MemberRole] = mapped_column(
        PgEnum(MemberRole, name="member_role", schema="shop", create_type=False),
        default=MemberRole.USER,  # 기본 역할은 일반 회원
    )
    status: Mapped[MemberStatus] = mapped_column(
        PgEnum(MemberStatus, name="member_status", schema="shop", create_type=False),
        default=MemberStatus.ACTIVE,  # 기본 상태는 정상 이용
    )

    # 회원 등급 번호. member_grades 테이블의 grade_id를 참조한다.
    grade_id: Mapped[int] = mapped_column(
        SmallInteger,
        ForeignKey("shop.member_grades.grade_id"),
        default=1,
    )

    point_balance: Mapped[int] = mapped_column(Integer, default=0)  # 현재 보유 포인트
    total_paid: Mapped[float] = mapped_column(Numeric(14, 0), default=0)  # 누적 결제 금액
    order_count: Mapped[int] = mapped_column(Integer, default=0)  # 주문 횟수

    marketing_agree: Mapped[bool] = mapped_column(Boolean, default=False)  # 마케팅 정보 수신 동의
    sms_agree: Mapped[bool] = mapped_column(Boolean, default=False)  # 문자 수신 동의
    email_agree: Mapped[bool] = mapped_column(Boolean, default=False)  # 이메일 수신 동의

    oauth_provider: Mapped[Optional[str]] = mapped_column(String(20))  # 가입에 사용한 외부 로그인 서비스
    oauth_id: Mapped[Optional[str]] = mapped_column(String(190))  # 외부 서비스에서 발급한 회원 식별값
    profile_image: Mapped[Optional[str]] = mapped_column(String(255))  # 프로필 이미지 경로나 URL

    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))  # 마지막 로그인 시각
    login_fail_cnt: Mapped[int] = mapped_column(SmallInteger, default=0)  # 로그인 실패 횟수

    # server_default가 설정되어 있어 DB가 현재 시각을 넣는다.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    withdrawn_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))  # 탈퇴 처리 시각

    # 회원 등급을 조회할 때 등급 정보도 함께 가져오도록 설정한다.
    grade: Mapped["MemberGrade"] = relationship(
        back_populates="members",
        lazy="joined",
    )

    # 한 회원은 여러 배송지를 가질 수 있다.
    # 회원이 삭제되면 연결된 배송지도 함께 정리한다.
    addresses: Mapped[List["MemberAddress"]] = relationship(
        back_populates="member",
        cascade="all, delete-orphan",
    )

    @property
    def is_admin(self) -> bool:
        """관리자나 직원이면 True를 반환한다."""
        return self.role in (MemberRole.ADMIN, MemberRole.STAFF)

    @property
    def masked_email(self) -> str:
        """이메일 앞부분을 일부 가린 문자열을 만든다."""
        # partition("@")은 이메일을 아이디 부분과 도메인 부분으로 나눈다.
        local, _, domain = self.email.partition("@")

        # 아이디가 짧으면 첫 글자만 보이고 나머지를 *로 가린다.
        if len(local) <= 2:
            return f"{local[0]}*@{domain}"

        # 아이디 앞 두 글자는 보이고 나머지는 *로 가린다.
        return f"{local[:2]}{'*' * (len(local) - 2)}@{domain}"

    def __repr__(self) -> str:  # pragma: no cover
        """개발자가 객체 내용을 확인할 때 사용할 문자열."""
        return f"<Member {self.member_id} {self.email}>"


class MemberAddress(Base):
    """회원의 배송지 정보를 저장하는 테이블."""

    __tablename__ = "member_addresses"
    __table_args__ = {"schema": "shop"}

    address_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # 배송지 번호

    # 배송지 소유 회원 번호. 회원이 삭제되면 배송지도 DB에서 삭제한다.
    member_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("shop.members.member_id", ondelete="CASCADE"),
    )

    alias: Mapped[str] = mapped_column(String(50), default="기본 배송지")  # 배송지 구분명
    receiver: Mapped[str] = mapped_column(String(60), nullable=False)  # 받는 사람
    phone: Mapped[str] = mapped_column(String(20), nullable=False)  # 받는 사람 전화번호
    zipcode: Mapped[str] = mapped_column(String(10), nullable=False)  # 우편번호
    address1: Mapped[str] = mapped_column(String(255), nullable=False)  # 기본 주소
    address2: Mapped[Optional[str]] = mapped_column(String(255))  # 상세 주소
    request_memo: Mapped[Optional[str]] = mapped_column(String(255))  # 배송 요청 사항
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)  # 기본 배송지인지 여부

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # 이 배송지가 어느 회원에게 속하는지 나타낸다.
    member: Mapped["Member"] = relationship(back_populates="addresses")


class MemberWithdrawal(Base):
    """회원 탈퇴 시점의 정보를 기록하는 테이블."""

    __tablename__ = "member_withdrawals"
    __table_args__ = {"schema": "shop"}

    withdrawal_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # 탈퇴 기록 번호
    member_id: Mapped[int] = mapped_column(BigInteger, nullable=False)  # 탈퇴한 회원 번호
    email_masked: Mapped[str] = mapped_column(String(190), nullable=False)  # 가린 이메일
    reason_code: Mapped[str] = mapped_column(String(40), nullable=False)  # 탈퇴 사유 분류
    reason_text: Mapped[Optional[str]] = mapped_column(Text)  # 사용자가 입력한 상세 사유
    total_paid: Mapped[float] = mapped_column(Numeric(14, 0), default=0)  # 탈퇴 시점의 누적 결제액
    joined_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))  # 가입 시각
    withdrawn_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )  # 탈퇴 기록 생성 시각


class PointHistory(Base):
    """포인트가 적립되거나 사용된 내역을 저장하는 테이블."""

    __tablename__ = "point_histories"
    __table_args__ = {"schema": "shop"}

    point_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # 포인트 내역 번호

    # 내역의 소유 회원. 회원이 삭제되면 포인트 내역도 삭제된다.
    member_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("shop.members.member_id", ondelete="CASCADE"),
    )

    # 포인트가 생기거나 사용된 이유를 정해진 ENUM 값으로 저장한다.
    reason: Mapped[PointReason] = mapped_column(
        PgEnum(PointReason, name="point_reason", schema="shop", create_type=False)
    )

    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # 이번에 적립되거나 사용된 포인트
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)  # 처리 후 남은 포인트
    ref_id: Mapped[Optional[int]] = mapped_column(BigInteger)  # 관련 주문 등의 번호
    memo: Mapped[Optional[str]] = mapped_column(String(200))  # 추가 설명
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))  # 포인트 만료 시각

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class LoginHistory(Base):
    """로그인 시도 기록을 저장하는 로그 테이블."""

    __tablename__ = "login_histories"
    __table_args__ = {"schema": "log"}  # 서비스 데이터와 별도로 log 스키마에 저장

    login_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # 로그인 기록 번호
    member_id: Mapped[Optional[int]] = mapped_column(BigInteger)  # 회원을 찾았으면 회원 번호
    email: Mapped[Optional[str]] = mapped_column(String(190))  # 로그인 시 입력한 이메일
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)  # 로그인 성공 여부
    ip_address: Mapped[Optional[str]] = mapped_column(String(50))  # 접속한 IP 주소
    user_agent: Mapped[Optional[str]] = mapped_column(String(400))  # 브라우저·기기 정보

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )