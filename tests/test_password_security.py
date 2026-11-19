import bcrypt
import pytest
from fastapi import HTTPException

from app.core.security import hash_password, validate_password_policy, verify_password


def test_bcrypt_hash_round_trip_and_existing_hash():
    password = 'Booktest1234'
    stored = hash_password(password)
    assert verify_password(password, stored)
    assert not verify_password('wrong-password', stored)
    existing = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    assert verify_password(password, existing)
    assert not verify_password(password, 'invalid-hash')


def test_password_byte_limit_is_reported_without_truncation():
    too_long = '가' * 24 + 'a1'
    with pytest.raises(HTTPException) as exc:
        validate_password_policy(too_long)
    assert exc.value.status_code == 400
    with pytest.raises(HTTPException):
        hash_password(too_long)
    assert not verify_password(too_long, '$2b$12$QQt8BG3/GaLkE6VWxfcNL.kEHYuq0Q9Jm0kV5iVZk0.04Fu8B0r.C')
