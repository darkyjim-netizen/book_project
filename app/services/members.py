# app/services/members.py

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Member
from app.schemas import MemberCreate
from app.security import hash_password


def get_member_by_username(
    db: Session,
    username: str,
) -> Member | None:
    return db.scalar(
        select(Member).where(Member.username == username)
    )


def get_member_by_email(
    db: Session,
    email: str,
) -> Member | None:
    return db.scalar(
        select(Member).where(Member.email == email)
    )


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
        db.commit()
        db.refresh(member)
    except Exception:
        db.rollback()
        raise

    return member


def list_members(
    db: Session,
    page: int = 1,
    size: int = 20,
) -> tuple[list[Member], int]:
    from sqlalchemy import func

    total = db.scalar(
        select(func.count()).select_from(Member)
    ) or 0

    statement = (
        select(Member)
        .order_by(Member.id)
        .offset((page - 1) * size)
        .limit(size)
    )

    items = list(db.scalars(statement).all())
    return items, total