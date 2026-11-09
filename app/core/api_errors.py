from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


# 상태 코드와 공통 오류 형식으로 HTTP 예외를 생성합니다.
def api_error(status: int, code: str, message: str) -> HTTPException:
    # 401 응답에는 Bearer 인증이 필요하다는 헤더를 함께 설정합니다.
    headers = {"WWW-Authenticate": "Bearer"} if status == 401 else None
    return HTTPException(status, {"code": code, "message": message}, headers)


# API 오류는 공통 형식으로, 나머지 오류는 detail 형식으로 응답합니다.
async def http_error(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api/") and isinstance(exc.detail, dict):
        return JSONResponse(exc.detail, status_code=exc.status_code, headers=exc.headers)
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers)


# API 입력 검증 오류를 필드별 설명이 포함된 400 응답으로 변환합니다.
async def validation_error(request: Request, exc: RequestValidationError):
    from fastapi.exception_handlers import request_validation_exception_handler

    if not request.url.path.startswith("/api/"):
        return await request_validation_exception_handler(request, exc)
    return JSONResponse(
        {"code": "INVALID_INPUT_VALUE", "message": "요청 값을 확인해 주세요.",
         "fields": [{"field": ".".join(map(str, error["loc"])), "message": error["msg"]}
                    for error in exc.errors()]},
        status_code=400,
    )
