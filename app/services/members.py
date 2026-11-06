# app/services/members.py

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Member
from app.schemas import MemberCreate
from app.security import hash_password


# 데이터베이스에서 사용자 아이디를 기준으로 회원 정보를 조회합니다.
def get_member_by_username(
    db: Session,
    username: str,
) -> Member | None:
    return db.scalar(
        select(Member).where(Member.username == username)
    )


# 데이터베이스에서 이메일을 기준으로 회원 정보를 조회합니다.
def get_member_by_email(
    db: Session,
    email: str,
) -> Member | None:
    return db.scalar(
        select(Member).where(Member.email == email)
    )


# 중복 검증을 거친 후 비밀번호를 암호화하여 새로운 회원 정보를 데이터베이스에 저장합니다.
def create_member(
    db: Session,
    data: MemberCreate,
) -> Member:
    if get_member_by_username(db, data.username):
        raise ValueError("이미 사용 중인 아이디입니다.")

    if get_member_by_email(db, str(data.email)):
        raise ValueError("이미 사용 중인 이메일입니다.")

    member = Member(
        username=data.username,
        email=str(data.email),
        password_hash=hash_password(data.password),
        display_name=data.display_name,
        role="member",
        is_active=True,
    )

    db.add(member)

    try:
        db.commit()  # 트랜잭션을 커밋하여 DB에 반영합니다.
        db.refresh(member)  # 최신 데이터로 회원 객체를 갱신합니다.
    except Exception:
        db.rollback()  # 오류 발생 시 변경 사항을 취소합니다.
        raise

    return member


# 전체 회원 목록을 페이징 처리하여 조회하고 전체 회원 수도 함께 반환합니다.
def list_members(
    db: Session,
    page: int = 1,
    size: int = 20,
) -> tuple[list[Member], int]:
    from sqlalchemy import func

    total = db.scalar(
        select(func.count()).select_from(Member)
    ) or 0  # 전체 회원 수를 조회합니다.

    statement = (
        select(Member)
        .order_by(Member.id)
        .offset((page - 1) * size)
        .limit(size)
    )  # 페이지네이션 조건이 적용된 쿼리를 생성합니다.

    items = list(db.scalars(statement).all())
    return items, total