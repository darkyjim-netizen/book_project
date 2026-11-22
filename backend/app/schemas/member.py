"""회원 기능에서 주고받는 요청과 응답 데이터 형식."""
from datetime import date, datetime
from typing import List, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)


# -----------------------------------------------------------------------------
# 인증
# -----------------------------------------------------------------------------
class SignupRequest(BaseModel):
    """회원가입 요청으로 받을 데이터와 입력 검증 규칙."""

    email: EmailStr = Field(..., description="로그인 이메일")  # 올바른 이메일 형식이어야 한다.
    password: str = Field(..., min_length=8, max_length=64)  # 필수 비밀번호, 8~64자
    password_confirm: str = Field(..., min_length=8, max_length=64)  # 비밀번호 확인 입력
    name: str = Field(..., min_length=1, max_length=60)  # 필수 이름
    nickname: Optional[str] = Field(None, max_length=60)  # 선택 별명
    phone: Optional[str] = Field(
        None,
        max_length=20,
        examples=["010-1234-5678"],
    )  # 선택 전화번호. 검증 후 하이픈 형식으로 정리한다.
    birth_date: Optional[date] = None  # 생년월일. YYYY-MM-DD 형식의 날짜
    gender: str = Field("N", pattern="^[MFN]$")  # M, F, N 중 하나. 기본값은 미입력
    marketing_agree: bool = False  # 마케팅 수신 동의 여부
    sms_agree: bool = False  # 문자 수신 동의 여부
    email_agree: bool = False  # 이메일 수신 동의 여부

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, v: str) -> str:
        """공백만 있는 이름은 받지 않는다. 앞뒤 공백은 지워서 저장한다."""
        v = v.strip()
        if not v:
            raise ValueError("이름을 입력해 주세요.")
        return v

    @field_validator("password_confirm")
    @classmethod
    def _match(cls, v: str, info):
        """비밀번호와 비밀번호 확인 값이 같은지 검사한다."""

        # info.data에는 이 필드보다 앞서 검증된 값들이 들어 있다.
        # password가 먼저 선언되어 있으므로 여기서 비교할 수 있다.
        if info.data.get("password") and v != info.data["password"]:
            raise ValueError("비밀번호가 일치하지 않습니다.")
        return v

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: Optional[str]):
        """전화번호에서 숫자만 추려 형식을 통일한다."""

        # 전화번호를 입력하지 않았다면 None을 그대로 둔다.
        if v is None:
            return v

        # 하이픈, 공백 등 숫자가 아닌 문자를 제거한다.
        digits = "".join(ch for ch in v if ch.isdigit())

        # 휴대폰 번호는 숫자 기준 10자리 또는 11자리만 허용한다.
        if len(digits) not in (10, 11):
            raise ValueError("휴대폰 번호 형식이 올바르지 않습니다.")

        # 01012345678 같은 입력을 010-1234-5678 형식으로 바꾼다.
        return f"{digits[:3]}-{digits[3:-4]}-{digits[-4:]}"


class LoginRequest(BaseModel):
    """로그인 요청 데이터."""

    email: EmailStr  # 로그인할 이메일
    password: str  # 비밀번호


class TokenResponse(BaseModel):
    """로그인 성공 후 반환할 토큰과 회원 정보."""

    access_token: str  # API 요청 인증에 사용하는 짧은 만료 토큰
    refresh_token: str  # 새 access token을 발급받을 때 사용하는 토큰
    token_type: str = "bearer"  # 토큰 사용 방식
    expires_in: int  # access token 만료까지 남은 시간(보통 초 단위)
    member: "MemberResponse"  # 로그인한 회원의 공개 정보


class RefreshRequest(BaseModel):
    """새 access token을 요청할 때 보낼 데이터."""

    refresh_token: str


class PasswordChangeRequest(BaseModel):
    """로그인한 회원이 비밀번호를 바꿀 때 보낼 데이터."""

    current_password: str  # 본인 확인용 현재 비밀번호
    new_password: str = Field(..., min_length=8, max_length=64)  # 새 비밀번호


class PasswordResetRequest(BaseModel):
    """비밀번호 재설정 절차를 시작할 때 보낼 이메일."""

    email: EmailStr


# -----------------------------------------------------------------------------
# 회원
# -----------------------------------------------------------------------------
class MemberGradeResponse(BaseModel):
    """회원 등급 응답에 포함할 항목."""

    # SQLAlchemy 모델 객체에서 속성값을 읽어 Pydantic 데이터로 변환한다.
    model_config = ConfigDict(from_attributes=True)

    grade_id: int  # 등급 번호
    grade_code: str  # 등급 내부 코드
    grade_name: str  # 화면에 표시할 등급명
    discount_rate: float  # 등급 할인율
    point_rate: float  # 등급 포인트 적립률
    free_ship_limit: float  # 무료 배송 적용 기준 금액


class MemberResponse(BaseModel):
    """회원 정보를 API 응답으로 보낼 때 사용할 형식."""

    # 딕셔너리뿐 아니라 SQLAlchemy 객체의 속성에서도 값을 읽는다.
    model_config = ConfigDict(from_attributes=True)

    member_id: int  # 회원 번호
    email: str  # 이메일
    name: str  # 이름
    nickname: Optional[str] = None  # 별명
    phone: Optional[str] = None  # 전화번호
    gender: str  # 성별 코드
    role: str  # 회원 역할
    status: str  # 계정 상태
    point_balance: int  # 현재 포인트
    total_paid: float  # 누적 결제 금액
    order_count: int  # 주문 횟수
    grade: Optional[MemberGradeResponse] = None  # 회원 등급 정보
    created_at: datetime  # 가입 시각
    last_login_at: Optional[datetime] = None  # 마지막 로그인 시각

    @field_validator("gender", "role", "status", mode="before")
    @classmethod
    def _enum_value(cls, v):
        """Enum 객체가 들어오면 실제 문자열 값으로 변환한다."""

        # 예: MemberRole.USER가 들어오면 "USER"를 응답에 넣는다.
        # 이미 문자열이면 그대로 둔다.
        return v.value if hasattr(v, "value") else v


class MemberUpdateRequest(BaseModel):
    """회원 정보 수정 요청. 값이 None이면 수정하지 않는 방식으로 사용할 수 있다."""

    name: Optional[str] = Field(None, max_length=60)
    nickname: Optional[str] = Field(None, max_length=60)
    phone: Optional[str] = Field(None, max_length=20)
    birth_date: Optional[date] = None
    gender: Optional[str] = Field(None, pattern="^[MFN]$")
    marketing_agree: Optional[bool] = None
    sms_agree: Optional[bool] = None
    email_agree: Optional[bool] = None


class WithdrawRequest(BaseModel):
    """회원 탈퇴 요청 데이터."""

    password: Optional[str] = None  # 탈퇴 전 비밀번호 확인이 필요하면 사용
    reason_code: str = Field("ETC", max_length=40)  # 탈퇴 사유 분류 코드
    reason_text: Optional[str] = None  # 사용자가 적은 구체적인 사유


# -----------------------------------------------------------------------------
# 배송지
# -----------------------------------------------------------------------------
class AddressCreateRequest(BaseModel):
    """새 배송지를 등록할 때 받을 데이터."""

    alias: str = Field("기본 배송지", max_length=50)  # 배송지 별칭
    receiver: str = Field(..., max_length=60)  # 받는 사람 이름
    phone: str = Field(..., max_length=20)  # 받는 사람 전화번호
    zipcode: str = Field(..., max_length=10)  # 우편번호
    address1: str = Field(..., max_length=255)  # 기본 주소
    address2: Optional[str] = Field(None, max_length=255)  # 상세 주소
    request_memo: Optional[str] = Field(None, max_length=255)  # 배송 요청 사항
    is_default: bool = False  # 기본 배송지로 설정할지 여부


class AddressResponse(BaseModel):
    """배송지 정보를 응답할 때 사용할 형식."""

    model_config = ConfigDict(from_attributes=True)  # ORM 객체의 속성을 읽는다.

    address_id: int  # 배송지 번호
    alias: str  # 배송지 별칭
    receiver: str  # 받는 사람
    phone: str  # 전화번호
    zipcode: str  # 우편번호
    address1: str  # 기본 주소
    address2: Optional[str] = None  # 상세 주소
    request_memo: Optional[str] = None  # 배송 요청 사항
    is_default: bool  # 기본 배송지 여부


# -----------------------------------------------------------------------------
# 포인트 / 쿠폰
# -----------------------------------------------------------------------------
class PointHistoryResponse(BaseModel):
    """포인트 적립·사용 내역을 응답할 때 사용할 형식."""

    model_config = ConfigDict(from_attributes=True)  # ORM 객체의 속성을 읽는다.

    point_id: int  # 포인트 내역 번호
    reason: str  # 적립 또는 사용 이유
    amount: int  # 변동된 포인트
    balance_after: int  # 처리 후 잔액
    memo: Optional[str] = None  # 상세 설명
    created_at: datetime  # 처리 시각

    @field_validator("reason", mode="before")
    @classmethod
    def _enum_value(cls, v):
        """포인트 사유가 Enum이면 문자열 값으로 변환한다."""
        return v.value if hasattr(v, "value") else v


class CouponResponse(BaseModel):
    """회원에게 발급된 쿠폰 정보를 응답할 때 사용할 형식."""

    model_config = ConfigDict(from_attributes=True)  # ORM 객체의 속성을 읽는다.

    member_coupon_id: int  # 회원 쿠폰 발급 기록 번호
    coupon_id: int  # 쿠폰 종류 번호
    name: str  # 쿠폰 이름
    coupon_type: str  # 정액, 정률, 무료 배송 등 쿠폰 유형
    discount_value: float  # 할인 금액 또는 할인율
    max_discount: Optional[float] = None  # 최대 할인액
    min_order_amount: float  # 쿠폰 사용을 위한 최소 주문 금액
    is_used: bool  # 이미 사용했는지 여부
    expires_at: datetime  # 회원 쿠폰의 만료 시각


class MemberStatsResponse(BaseModel):
    """마이페이지에 표시할 회원 활동 요약."""

    order_count: int  # 전체 주문 수
    shipping_count: int  # 배송 중인 주문 수
    point_balance: int  # 현재 포인트
    coupon_count: int  # 보유 쿠폰 수
    review_count: int  # 작성한 리뷰 수
    wishlist_count: int  # 위시리스트에 담은 도서 수
    grade_name: str  # 현재 회원 등급명
    next_grade_name: Optional[str] = None  # 다음 등급명. 최고 등급이면 없을 수 있다.
    next_grade_remain: Optional[float] = None  # 다음 등급까지 필요한 금액


# TokenResponse에서 아직 아래쪽에 정의된 MemberResponse를 참조하므로,
# 모든 클래스 정의가 끝난 뒤 참조할 타입을 다시 확인하도록 한다.
TokenResponse.model_rebuild()