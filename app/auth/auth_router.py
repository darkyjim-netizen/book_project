from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import auth_service
from app.auth.auth_dependencies import current_member
from app.auth.auth_schemas import LoginRequest, MemberMeResponse, RefreshRequest, SignupRequest, TokenResponse
from app.database import get_db
from app.models.user_model import Member


router = APIRouter(prefix="/api/auth", tags=["인증"])


@router.post("/signup", status_code=201, response_model=MemberMeResponse)
def signup(data: SignupRequest, db: Session = Depends(get_db)):
    return auth_service.signup(data, db)


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    return auth_service.login(data, db)


@router.post("/refresh", response_model=TokenResponse)
def refresh(data: RefreshRequest, db: Session = Depends(get_db)):
    return auth_service.refresh(data, db)


@router.get("/me", response_model=MemberMeResponse)
def me(member: Member = Depends(current_member)):
    return member
