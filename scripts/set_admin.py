"""관리자 계정의 이메일, 이름, 비밀번호를 새로 지정한다.

실행 (backend 폴더에서, 가상환경을 켠 상태로):
    python scripts/set_admin.py                # member_id 1번 계정을 관리자로 다시 지정
    python scripts/set_admin.py --member-id 7  # 다른 계정을 지정

- 이메일, 이름, 비밀번호는 실행 중에 물어본다 (비밀번호는 화면에 보이지 않는다).
- 비밀번호는 서버가 로그인 때 쓰는 것과 같은 방식(bcrypt)으로 암호화해서 저장한다.
- 계정의 role 은 ADMIN, status 는 ACTIVE 로 바뀌고 로그인 실패 횟수는 0으로 초기화된다.
- 마지막에 "yes" 를 입력해야 실제로 저장된다.
"""
import argparse
import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import engine  # noqa: E402
from app.core.security import hash_password  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--member-id", type=int, default=1, help="관리자로 지정할 member_id (기본 1)")
    mid = ap.parse_args().member_id

    with engine.connect() as c:
        cur = c.execute(
            text("SELECT email, name, role::text FROM shop.members WHERE member_id = :m"),
            {"m": mid},
        ).first()
    if cur is None:
        sys.exit(f"member_id {mid} 계정이 없습니다.")
    print(f"현재 계정: member_id={mid}, 이메일={cur[0]}, 이름={cur[1]}, 역할={cur[2]}")

    email = input("새 이메일: ").strip()
    name = input("새 이름: ").strip()
    pw = getpass.getpass("새 비밀번호: ")
    if getpass.getpass("비밀번호 다시 입력: ") != pw:
        sys.exit("비밀번호가 서로 다릅니다.")
    if "@" not in email or not name:
        sys.exit("이메일 형식이나 이름이 올바르지 않습니다.")
    if len(pw) < settings.PASSWORD_MIN_LENGTH:
        sys.exit(f"비밀번호는 {settings.PASSWORD_MIN_LENGTH}자 이상이어야 합니다.")

    with engine.connect() as c:
        dup = c.execute(
            text("SELECT member_id FROM shop.members WHERE email = :e AND member_id <> :m"),
            {"e": email, "m": mid},
        ).first()
    if dup:
        sys.exit(f"이미 다른 계정(member_id={dup[0]})이 쓰는 이메일입니다.")

    print(f"\n저장할 내용: member_id={mid} -> 이메일={email}, 이름={name}, 역할=ADMIN (비밀번호는 암호화해서 저장)")
    if input("저장할까요? (yes 입력): ").strip().lower() != "yes":
        sys.exit("취소했습니다. 아무것도 바꾸지 않았습니다.")

    with engine.begin() as c:
        n = c.execute(
            text("""UPDATE shop.members
                       SET email = :e, name = :n, password_hash = :h,
                           role = 'ADMIN', status = 'ACTIVE', login_fail_cnt = 0,
                           updated_at = now()
                     WHERE member_id = :m"""),
            {"e": email, "n": name, "h": hash_password(pw), "m": mid},
        ).rowcount
    print(f"완료: {n}개 계정을 갱신했습니다. 이제 이 이메일과 새 비밀번호로 로그인하세요.")


if __name__ == "__main__":
    main()
