from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.jwt_tokens import token_member_id
from app.core.api_errors import api_error
from app.database import get_db
from app.models.user_model import Member


bearer = HTTPBearer(auto_error=False)


def active_member(db: Session, member_id: int) -> Member:
    member = db.get(Member, member_id)
    if member is None:
        raise api_error(401, "MEMBER_NOT_FOUND", "회원을 찾을 수 없습니다.")
    if not member.is_active:
        raise api_error(401, "UNAUTHORIZED_ACCESS", "활성 회원만 이용할 수 있습니다.")
    return member


def current_member(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> Member:
    if credentials is None:
        raise api_error(401, "UNAUTHORIZED_ACCESS", "로그인이 필요합니다.")
    return active_member(db, token_member_id(credentials.credentials, "access"))


def admin_member(member: Member = Depends(current_member)) -> Member:
    if member.role != "admin":
        raise api_error(403, "ADMIN_PERMISSION_REQUIRED", "관리자 권한이 필요합니다.")
    return member
