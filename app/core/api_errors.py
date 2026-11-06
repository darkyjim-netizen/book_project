from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def api_error(status: int, code: str, message: str) -> HTTPException:
    headers = {"WWW-Authenticate": "Bearer"} if status == 401 else None
    return HTTPException(status, {"code": code, "message": message}, headers)


async def http_error(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api/") and isinstance(exc.detail, dict):
        return JSONResponse(exc.detail, status_code=exc.status_code, headers=exc.headers)
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers)


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
