from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.auth_dependencies import active_member
from app.auth.auth_schemas import LoginRequest, RefreshRequest, SignupRequest
from app.auth.jwt_tokens import issue_tokens, token_member_id
from app.core.api_errors import api_error
from app.core.security import verify_password
from app.crud.user_crud import create_member, get_member_by_email
from app.routers.member_schemas import MemberCreate


# 고유 아이디로 회원을 생성하고 이메일 중복 오류를 처리합니다.
def signup(data: SignupRequest, db: Session):
    # 검증된 이메일을 회원 생성과 중복 조회에 사용할 문자열로 바꿉니다.
    email = str(data.email)
    try:
        return create_member(db, MemberCreate(
            username=f"user_{uuid4().hex}", email=email, password=data.password,
            display_name=data.name,
        ))
    # 회원 생성 실패가 이메일 중복 때문이면 공통 API 오류로 바꿉니다.
    except (ValueError, IntegrityError):
        if get_member_by_email(db, email):
            raise api_error(400, "DUPLICATE_EMAIL", "이미 등록된 이메일입니다.") from None
        raise


# 회원 상태와 비밀번호를 확인한 후 인증 토큰을 발급합니다.
def login(data: LoginRequest, db: Session):
    member = get_member_by_email(db, str(data.email))
    if member is None or not member.is_active or not verify_password(data.password, member.password_hash):
        raise api_error(401, "UNAUTHORIZED_ACCESS", "이메일 또는 비밀번호가 올바르지 않습니다.")
    return issue_tokens(member.id)


# 리프레시 토큰과 회원 상태를 확인한 후 인증 토큰을 재발급합니다.
def refresh(data: RefreshRequest, db: Session):
    member = active_member(db, token_member_id(data.refresh_token, "refresh"))
    return issue_tokens(member.id)
