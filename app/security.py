# app/security.py

from pwdlib import PasswordHash

# 권장되는 보안 설정(알고리즘 등)을 사용하는 비밀번호 해싱 객체를 생성합니다.
password_hash = PasswordHash.recommended()


# 평문 비밀번호를 안전하게 암호화(해싱)하여 반환합니다.
def hash_password(password: str) -> str:
    return password_hash.hash(password)


# 사용자가 입력한 평문 비밀번호와 저장된 해시값이 일치하는지 검증합니다.
def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    return password_hash.verify(
        plain_password,
        hashed_password,
    )


# 테스트 또는 초기 설정을 위해 비밀번호를 미리 해싱합니다.
hashed = hash_password("my-secret-password")