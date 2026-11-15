from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.jwt_tokens import token_member_id
from app.core.api_errors import api_error
from app.database import get_db
from app.models.user_model import Member


# Authorization 헤더에서 Bearer 토큰을 읽고 누락 오류는 직접 처리합니다.
bearer = HTTPBearer(auto_error=False)


# 회원 ID로 계정을 조회하고 존재 여부와 활성 상태를 확인합니다.
def active_member(db: Session, member_id: int) -> Member:
    member = db.get(Member, member_id)
    if member is None:
        raise api_error(401, "MEMBER_NOT_FOUND", "회원을 찾을 수 없습니다.")
    if not member.is_active:
        raise api_error(401, "UNAUTHORIZED_ACCESS", "활성 회원만 이용할 수 있습니다.")
    return member


# 요청의 액세스 토큰을 검증하여 현재 로그인한 회원을 반환합니다.
def current_member(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> Member:
    if credentials is None:
        raise api_error(401, "UNAUTHORIZED_ACCESS", "로그인이 필요합니다.")
    return active_member(db, token_member_id(credentials.credentials, "access"))


# 현재 회원이 관리자 권한을 가졌는지 확인합니다.
def admin_member(member: Member = Depends(current_member)) -> Member:
    if member.role != "admin":
        raise api_error(403, "ADMIN_PERMISSION_REQUIRED", "관리자 권한이 필요합니다.")
    return member
