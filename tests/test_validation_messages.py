import json

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from app.core.exceptions import register_exception_handlers


def test_email_validation_uses_korean_message_in_existing_envelope():
    app = FastAPI()
    register_exception_handlers(app)
    for location in [("query", "email"), ("body", "email")]:
        error = RequestValidationError([{"loc": location, "msg": "value is not a valid email address: It should have a period.", "type": "value_error"}])
        handler = app.exception_handlers[RequestValidationError](None, error)
        try:
            handler.send(None)
        except StopIteration as completed:
            response = completed.value
        body = json.loads(response.body)
        assert response.status_code == 422
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert body["error"]["detail"][0]["msg"] == "올바른 이메일 형식으로 입력해 주세요. (예: name@example.com)"
        assert "test@com" not in response.body.decode()
