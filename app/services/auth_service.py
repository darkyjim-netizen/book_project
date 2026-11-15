"""회원 인증과 계정 관리 서비스."""
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select  # ORM 조회문을 만드는 도구
from sqlalchemy.orm import Session  # DB 세션 타입

from app.core.config import settings  # 로그인 제한, 토큰 만료 시간 등 설정
from app.core.exceptions import BusinessError, NotFoundError  # 업무 오류 예외
from app.core.security import (
    create_access_token,   # API 요청용 액세스 토큰 생성
    create_refresh_token,  # 액세스 토큰 재발급용 토큰 생성
    decode_token,          # 토큰을 해석하고 검증
    hash_password,         # 비밀번호를 해시로 변환
    validate_password_policy,  # 비밀번호 규칙 검사
    verify_password,       # 입력 비밀번호와 저장된 해시 비교
)
from app.models.enums import MemberStatus, PointReason
from app.models.member import LoginHistory, Member, MemberWithdrawal, PointHistory
from app.models.promotion import Coupon, MemberCoupon
from app.schemas.member import LoginRequest, SignupRequest

logger = logging.getLogger(__name__)  # 이 파일의 로그를 기록할 로거

WELCOME_POINT = 1000  # 회원가입 시 지급할 포인트
WELCOME_COUPON_CODE = "WELCOME3000"  # 가입 축하 쿠폰의 코드


class AuthService:
    """회원 인증과 계정 관련 작업을 처리한다."""

    def __init__(self, db: Session):
        self.db = db  # 서비스 메서드에서 사용할 DB 세션

    # ------------------------------------------------------------------ 가입
    def signup(self, payload: SignupRequest) -> Member:
        """회원 정보를 저장하고 가입 혜택을 지급한다."""

        # 같은 이메일로 가입한 회원이 있는지 확인한다.
        exists = self.db.scalar(
            select(Member).where(Member.email == payload.email)
        )
        if exists:
            raise BusinessError(
                "이미 사용 중인 이메일입니다.",
                code="EMAIL_DUPLICATED",
            )

        # 비밀번호가 프로젝트에서 정한 보안 규칙에 맞는지 검사한다.
        validate_password_policy(payload.password)

        # 요청으로 받은 정보를 새 회원 객체에 담는다.
        member = Member(
            email=payload.email,
            password_hash=hash_password(payload.password),  # 원문 대신 해시 저장
            name=payload.name,
            nickname=payload.nickname or payload.name,  # 별명이 없으면 이름을 사용
            phone=payload.phone,
            birth_date=payload.birth_date,
            gender=payload.gender,
            marketing_agree=payload.marketing_agree,
            sms_agree=payload.sms_agree,
            email_agree=payload.email_agree,
            grade_id=1,  # 신규 회원의 기본 등급
        )
        self.db.add(member)

        # INSERT를 먼저 실행해 member_id를 얻는다.
        # 아직 commit 전이므로 전체 작업이 확정된 것은 아니다.
        self.db.flush()

        # 회원 번호를 사용해 포인트와 쿠폰 지급 기록을 만든다.
        self._grant_welcome_benefits(member)

        # 회원, 포인트, 쿠폰 변경을 DB에 확정한다.
        self.db.commit()

        # DB에 저장된 값으로 회원 객체를 새로고침한다.
        self.db.refresh(member)

        logger.info(
            "신규 회원 가입: member_id=%s email=%s",
            member.member_id,
            member.email,
        )
        return member

    def _grant_welcome_benefits(self, member: Member) -> None:
        """가입 축하 포인트와 쿠폰을 지급한다."""

        # 현재 보유 포인트에 가입 축하 포인트를 더한다.
        member.point_balance = (member.point_balance or 0) + WELCOME_POINT

        # 포인트 잔액뿐 아니라 적립 사유도 내역 테이블에 기록한다.
        self.db.add(
            PointHistory(
                member_id=member.member_id,
                reason=PointReason.EVENT,
                amount=WELCOME_POINT,
                balance_after=member.point_balance,
                memo="회원가입 축하 포인트",
            )
        )

        # 가입 축하 쿠폰이 등록되어 있는지 확인한다.
        coupon = self.db.scalar(
            select(Coupon).where(Coupon.code == WELCOME_COUPON_CODE)
        )

        # 쿠폰이 존재하고 활성화된 경우 회원에게 발급한다.
        if coupon and coupon.is_active:
            self.db.add(
                MemberCoupon(
                    member_id=member.member_id,
                    coupon_id=coupon.coupon_id,
                    expires_at=coupon.valid_to,
                )
            )

            # 쿠폰의 전체 발급 수를 1 증가시킨다.
            coupon.issued_count = (coupon.issued_count or 0) + 1

    def check_email_available(self, email: str) -> bool:
        """해당 이메일을 가입에 사용할 수 있으면 True를 반환한다."""

        return self.db.scalar(
            select(Member).where(Member.email == email)
        ) is None

    # ------------------------------------------------------------------ 로그인
    def login(
        self,
        payload: LoginRequest,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> dict:
        """이메일과 비밀번호를 확인하고 토큰과 회원 정보를 반환한다."""

        # 입력한 이메일에 해당하는 회원을 찾는다.
        member = self.db.scalar(
            select(Member).where(Member.email == payload.email)
        )

        # 회원이 없거나 비밀번호가 틀리면 로그인 실패로 처리한다.
        if member is None or not verify_password(
            payload.password,
            member.password_hash,
        ):
            # 계정을 찾지 못했더라도 입력된 이메일로 실패 기록을 남긴다.
            self._write_login_history(
                member,
                payload.email,
                False,
                ip,
                user_agent,
            )

            # 회원이 존재하는 경우에만 연속 실패 횟수를 올린다.
            if member is not None:
                member.login_fail_cnt = (member.login_fail_cnt or 0) + 1

                # 설정된 실패 횟수에 도달하면 계정을 정지한다.
                if member.login_fail_cnt >= settings.LOGIN_FAIL_LIMIT:
                    member.status = MemberStatus.SUSPENDED
                    logger.warning(
                        "로그인 실패 한도 초과로 계정 정지: %s",
                        member.email,
                    )

            # 로그인 실패 기록과 실패 횟수 변경을 저장한다.
            self.db.commit()

            # 계정 존재 여부를 알 수 없도록 같은 오류 메시지를 사용한다.
            raise BusinessError(
                "이메일 또는 비밀번호가 올바르지 않습니다.",
                code="INVALID_CREDENTIALS",
                status_code=401,
            )

        # 탈퇴한 회원은 로그인할 수 없다.
        if member.status == MemberStatus.WITHDRAWN:
            raise BusinessError(
                "탈퇴한 계정입니다.",
                code="WITHDRAWN",
                status_code=403,
            )

        # 정지된 회원은 로그인할 수 없다.
        if member.status == MemberStatus.SUSPENDED:
            raise BusinessError(
                "정지된 계정입니다. 고객센터로 문의해 주세요.",
                code="SUSPENDED",
                status_code=403,
            )

        # 휴면 회원이 로그인하면 정상 이용 상태로 되돌린다.
        if member.status == MemberStatus.DORMANT:
            member.status = MemberStatus.ACTIVE
            logger.info("휴면 계정 복구: %s", member.email)

        # 로그인 실패 횟수를 초기화하고 마지막 로그인 시각을 갱신한다.
        member.login_fail_cnt = 0
        member.last_login_at = datetime.now(timezone.utc)

        # 성공한 로그인 기록을 남긴다.
        self._write_login_history(
            member,
            member.email,
            True,
            ip,
            user_agent,
        )

        # 상태, 로그인 기록, 마지막 로그인 시각을 저장한다.
        self.db.commit()
        self.db.refresh(member)

        # 토큰과 회원 정보를 호출한 쪽에 반환한다.
        return {
            "access_token": create_access_token(
                member.member_id,
                member.email,
                member.role.value,
            ),
            "refresh_token": create_refresh_token(member.member_id),
            # 설정은 분 단위이므로 토큰 응답에 맞춰 초 단위로 변환한다.
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "member": member,
        }

    def _write_login_history(
        self,
        member: Optional[Member],
        email: str,
        success: bool,
        ip: Optional[str],
        user_agent: Optional[str],
    ) -> None:
        """로그인 성공·실패 기록을 DB에 추가한다."""

        self.db.add(
            LoginHistory(
                # 회원을 찾지 못한 실패 기록이면 회원 번호는 비워 둔다.
                member_id=member.member_id if member else None,
                email=email,
                success=success,
                ip_address=ip,
                # 사용자 에이전트가 너무 길면 400자로 자른다.
                user_agent=(user_agent or "")[:400] or None,
            )
        )

    def refresh(self, refresh_token: str) -> dict:
        """유효한 리프레시 토큰으로 새 토큰 쌍을 발급한다."""

        # 토큰 서명, 만료 시간 등을 확인하고 내용을 읽는다.
        payload = decode_token(refresh_token)

        # 액세스 토큰을 잘못 전달한 경우 재발급을 거부한다.
        if payload.get("type") != "refresh":
            raise BusinessError(
                "리프레시 토큰이 아닙니다.",
                status_code=401,
            )

        # 토큰의 sub 값에서 회원 번호를 읽어 회원을 조회한다.
        member = self.db.get(Member, int(payload["sub"]))

        # 회원이 없거나 탈퇴 상태면 토큰을 재발급하지 않는다.
        if member is None or member.status == MemberStatus.WITHDRAWN:
            raise NotFoundError("회원을 찾을 수 없습니다.")

        return {
            "access_token": create_access_token(
                member.member_id,
                member.email,
                member.role.value,
            ),
            "refresh_token": create_refresh_token(member.member_id),
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "member": member,
        }

    # ---------------------------------------------------------------- 비밀번호
    def change_password(
        self,
        member: Member,
        current: str,
        new: str,
    ) -> None:
        """현재 비밀번호를 확인한 뒤 새 비밀번호로 변경한다."""

        # 입력한 현재 비밀번호가 저장된 해시와 일치하는지 확인한다.
        if not verify_password(current, member.password_hash):
            raise BusinessError("현재 비밀번호가 올바르지 않습니다.")

        # 현재 비밀번호와 같은 값으로 바꾸지 못하게 한다.
        if current == new:
            raise BusinessError("이전과 다른 비밀번호를 사용해 주세요.")

        # 새 비밀번호가 보안 정책에 맞는지 검사한다.
        validate_password_policy(new)

        # 새 비밀번호도 원문이 아닌 해시로 저장한다.
        member.password_hash = hash_password(new)
        self.db.commit()

        logger.info(
            "비밀번호 변경: member_id=%s",
            member.member_id,
        )

    def issue_temp_password(self, email: str) -> str:
        """임시 비밀번호를 만들고 DB에 저장한다.

        현재 코드는 생성한 값을 반환한다.
        실제 서비스에서는 안전한 전달 절차를 별도로 구현해야 한다.
        """
        import secrets  # 예측하기 어려운 임의 값을 만드는 보안 모듈
        import string  # 영문자와 숫자 목록을 가져오는 모듈

        # 이메일에 해당하는 회원을 찾는다.
        member = self.db.scalar(
            select(Member).where(Member.email == email)
        )
        if member is None:
            raise NotFoundError("가입되지 않은 이메일입니다.")

        # 임시 비밀번호에 사용할 영문자와 숫자 목록을 만든다.
        alphabet = string.ascii_letters + string.digits

        # 무작위 문자·숫자 10개 뒤에 "1a"를 붙여 임시 비밀번호를 만든다.
        temp = "".join(
            secrets.choice(alphabet)
            for _ in range(10)
        ) + "1a"

        # 임시 비밀번호도 해시한 값만 DB에 저장한다.
        member.password_hash = hash_password(temp)
        self.db.commit()

        logger.info("임시 비밀번호 발급: %s", email)

        # 호출한 쪽에 임시 비밀번호를 반환한다.
        return temp

    # ------------------------------------------------------------------ 탈퇴
    def withdraw(
        self,
        member: Member,
        reason_code: str,
        reason_text: Optional[str],
    ) -> None:
        """탈퇴 기록을 남기고 회원의 계정과 개인정보를 처리한다."""

        # 탈퇴 당시 이메일은 가린 형태로, 누적 구매액과 가입 시각은 기록으로 보관한다.
        self.db.add(
            MemberWithdrawal(
                member_id=member.member_id,
                email_masked=member.masked_email,
                reason_code=reason_code,
                reason_text=reason_text,
                total_paid=member.total_paid,
                joined_at=member.created_at,
            )
        )

        # 계정을 탈퇴 상태로 변경하고 탈퇴 시각을 기록한다.
        member.status = MemberStatus.WITHDRAWN
        member.withdrawn_at = datetime.now(timezone.utc)

        # 계정에서 개인 식별 정보를 바꾸거나 비운다.
        member.email = f"withdrawn_{member.member_id}@deleted.local"
        member.password_hash = None
        member.phone = None
        member.name = "탈퇴회원"
        member.nickname = "탈퇴회원"

        # 탈퇴 계정의 보유 포인트를 0으로 설정한다.
        member.point_balance = 0

        # 탈퇴 기록과 회원 정보 변경을 DB에 확정한다.
        self.db.commit()

        logger.info(
            "회원 탈퇴 완료: member_id=%s",
            member.member_id,
        )