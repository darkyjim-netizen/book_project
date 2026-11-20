from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from app.core.exceptions import BusinessError, NotFoundError
from app.schemas.member import SignupRequest
from app.services.auth_service import AuthService
from app.services.chat_service import ChatService


def payload(**changes):
    return SignupRequest(**{**dict(email="user@example.com", name="테스트", password="Booktest1234", password_confirm="Booktest1234"), **changes})


@pytest.mark.parametrize("existing,code", [([object()], "EMAIL_DUPLICATED")])
def test_signup_blocks_duplicates_before_writes(existing, code):
    db = Mock()
    db.scalar.side_effect = existing
    with pytest.raises(BusinessError) as exc:
        AuthService(db).signup(payload())
    assert exc.value.code == code
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_signup_rejects_blank_name():
    with pytest.raises(ValidationError):
        payload(name="   ")
    assert payload(name=" 테스트 ").name == "테스트"


@pytest.mark.parametrize("owner,current,admin,allowed", [(1, 1, False, True), (1, 2, False, False), (1, 2, True, True)])
def test_delete_room_checks_ownership(owner, current, admin, allowed):
    db = Mock()
    room = SimpleNamespace(member_id=owner)
    db.scalar.return_value = room
    member = SimpleNamespace(member_id=current, is_admin=admin)
    if allowed:
        ChatService(db).delete_room(10, member)
        db.delete.assert_called_once_with(room)
        db.commit.assert_called_once()
    else:
        with pytest.raises(BusinessError) as exc:
            ChatService(db).delete_room(10, member)
        assert exc.value.status_code == 403
        db.delete.assert_not_called()
        db.commit.assert_not_called()


def test_delete_missing_room():
    db = Mock()
    db.scalar.return_value = None
    with pytest.raises(NotFoundError):
        ChatService(db).delete_room(10, SimpleNamespace(member_id=1, is_admin=False))
    db.delete.assert_not_called()


def test_signup_allows_existing_name(monkeypatch):
    db = Mock()
    db.scalar.return_value = None  # Only email availability is queried.
    service = AuthService(db)
    monkeypatch.setattr(service, "_grant_welcome_benefits", Mock())
    monkeypatch.setattr("app.services.auth_service.hash_password", lambda password: "hashed")
    member = service.signup(payload(name="동명이인"))
    assert member.name == "동명이인"
    db.scalar.assert_called_once()
    db.commit.assert_called_once()
