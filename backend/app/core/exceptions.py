"""업무 처리 중 발생하는 예외와 API 오류 응답을 관리한다."""

import logging  # 오류와 처리 상황을 로그로 남긴다.
import traceback  # 예상하지 못한 오류의 상세 발생 위치를 기록한다.

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError  # 요청 데이터 검증 실패 예외
from fastapi.responses import JSONResponse  # JSON 형식의 HTTP 응답 생성
from sqlalchemy.exc import IntegrityError, SQLAlchemyError  # DB 관련 예외
from starlette.exceptions import HTTPException as StarletteHTTPException

# 이 이름으로 기록된 로그를 찾아볼 수 있다.
logger = logging.getLogger("bookstore")


class BusinessError(Exception):
    """쇼핑몰 업무 규칙을 위반했을 때 발생시키는 기본 예외."""

    status_code = status.HTTP_400_BAD_REQUEST
    code = "BUSINESS_ERROR"

    def __init__(
        self,
        message: str,
        code: str | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message

        # 로그인 서비스처럼 호출할 때 코드나 상태를 지정하면 기본값을 바꾼다.
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code


class NotFoundError(BusinessError):
    # 회원, 도서, 주문 등을 찾을 수 없으면 HTTP 404를 반환한다.
    status_code = status.HTTP_404_NOT_FOUND
    code = "NOT_FOUND"


class OutOfStockError(BusinessError):
    code = "OUT_OF_STOCK"


class PaymentError(BusinessError):
    code = "PAYMENT_FAILED"


class PermissionError_(BusinessError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "FORBIDDEN"


def _envelope(code: str, message: str, detail=None) -> dict:
    # 모든 처리기에서 같은 JSON 구조를 사용한다.
    error = {"code": code, "message": message}
    if detail is not None:
        error["detail"] = detail
    return {"success": False, "error": error}


def _validation_message(error: dict) -> str:
    field = error.get("loc", [""])[-1]
    label = {"email": "이메일", "nickname": "닉네임", "name": "이름", "password": "비밀번호", "password_confirm": "비밀번호 확인", "phone": "휴대전화", "birth_date": "생년월일"}.get(field, "입력값")
    if field == "email":
        return "올바른 이메일 형식으로 입력해 주세요. (예: name@example.com)"
    kind = error.get("type", "")
    context = error.get("ctx", {})
    if kind == "missing":
        return f"{label} 항목을 입력해 주세요."
    if kind == "string_too_short":
        return f"{label} 항목은 {context.get('min_length', 1)}자 이상 입력해 주세요."
    if kind == "string_too_long":
        return f"{label} 항목은 {context.get('max_length')}자 이하로 입력해 주세요."
    message = error.get("msg", "")
    if any("가" <= char <= "힣" for char in message):
        return message.removeprefix("Value error, ")
    return f"{label} 항목을 올바르게 입력해 주세요."


def register_exception_handlers(app: FastAPI) -> None:
    """main.py가 호출하면 FastAPI 앱에 공통 예외 처리기를 등록한다."""

    @app.exception_handler(BusinessError)
    async def handle_business(_request: Request, exc: BusinessError) -> JSONResponse:
        # NotFoundError, PaymentError 등 하위 예외도 여기서 처리한다.
        logger.warning("BusinessError %s: %s", exc.code, exc.message)
        return JSONResponse(
            content=_envelope(exc.code, exc.message),
            status_code=exc.status_code,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # 검증 오류의 위치, 메시지, 유형만 응답에 담는다.
        # 원본 입력과 JSON으로 변환하기 어려운 내부 정보는 제외한다.
        errors = [
            {"loc": error["loc"], "msg": _validation_message(error), "type": error["type"]}
            for error in exc.errors()
        ]
        return JSONResponse(
            content=_envelope("VALIDATION_ERROR", "입력값을 확인해 주세요.", errors),
            status_code=422,
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http(
        _request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        # 상태 코드와 WWW-Authenticate 같은 기존 HTTP 헤더를 전달한다.
        return JSONResponse(
            content=_envelope(f"HTTP_{exc.status_code}", str(exc.detail)),
            status_code=exc.status_code,
            headers=exc.headers,
        )

    @app.exception_handler(IntegrityError)
    async def handle_integrity(
        _request: Request, exc: IntegrityError
    ) -> JSONResponse:
        # 중복 데이터나 DB 제약 조건 위반은 HTTP 409로 처리한다.
        logger.exception("데이터베이스 제약 조건 위반")
        return JSONResponse(
            content=_envelope(
                "DB_CONFLICT", "이미 존재하는 데이터이거나 제약 조건을 위반했습니다."
            ),
            status_code=status.HTTP_409_CONFLICT,
        )

    @app.exception_handler(SQLAlchemyError)
    async def handle_database(
        _request: Request, exc: SQLAlchemyError
    ) -> JSONResponse:
        logger.exception("데이터베이스 처리 오류")
        return JSONResponse(
            content=_envelope("DB_ERROR", "데이터베이스 처리 중 오류가 발생했습니다."),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(_request: Request, exc: Exception) -> JSONResponse:
        # 상세 원인은 서버 로그에 기록하고, API에는 일반 오류 메시지를 보낸다.
        logger.exception("예상하지 못한 서버 오류")
        return JSONResponse(
            content=_envelope("INTERNAL_ERROR", "서버 내부 오류가 발생했습니다."),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
