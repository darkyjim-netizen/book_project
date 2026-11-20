from unittest.mock import Mock

import pytest

from app.core.exceptions import BusinessError, _validation_message
from app.routers.auth import check_nickname
from app.schemas.member import SignupRequest
from app.services.auth_service import AuthService


def test_duplicate_nickname_is_rejected_before_saving():
    db = Mock()
    db.scalar.side_effect = [None, 42]
    payload = SignupRequest(email="reader@example.com", name="독자", nickname="책친구",
                            password="Booktest1234", password_confirm="Booktest1234")
    with pytest.raises(BusinessError) as error:
        AuthService(db).signup(payload)
    assert error.value.code == "NICKNAME_DUPLICATED"
    assert error.value.message == "이미 사용 중인 닉네임입니다."
    db.add.assert_not_called()


def test_nickname_query_trims_and_ignores_case():
    db = Mock()
    db.scalar.return_value = None
    assert check_nickname(" Reader ", db) == {"nickname": "Reader", "available": True}
    query = db.scalar.call_args.args[0]
    assert "reader" in query.compile().params.values()


def test_blank_nickname_is_rejected():
    with pytest.raises(BusinessError, match="닉네임을 입력해 주세요"):
        AuthService(Mock()).check_nickname_available("   ")


def test_nickname_validation_is_korean():
    assert _validation_message({"loc": ("body", "nickname"), "type": "string_too_long",
                                "ctx": {"max_length": 60}}) == "닉네임 항목은 60자 이하로 입력해 주세요."
