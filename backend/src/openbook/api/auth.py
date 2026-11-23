"""비밀번호 해시와 로그인 토큰.

- 비밀번호는 scrypt(표준 라이브러리)로 해시해 저장한다. 원문은 어디에도 남기지 않는다.
- 토큰은 secrets로 만든 무작위 문자열이다. DB에는 SHA-256 해시만 저장한다 (DB가 새도 토큰을 못 씀).
- 로그·오류 문구에 이메일·비밀번호·토큰을 넣지 않는다.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

SESSION_DAYS = 30
_N, _R, _P = 2**14, 8, 1
_DUMMY = None  # 없는 이메일로 로그인할 때도 같은 시간이 걸리게 쓰는 해시


def _scrypt(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=32)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${_scrypt(password, salt).hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    global _DUMMY
    if not stored:
        _DUMMY = _DUMMY or hash_password("dummy-password")
        stored, real = _DUMMY, False
    else:
        real = True
    try:
        algo, n, r, p, salt, digest = stored.split("$")
        if algo != "scrypt":
            return False
        got = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(salt),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(bytes.fromhex(digest)),
        )
    except ValueError:
        return False
    return hmac.compare_digest(got.hex(), digest) and real


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def session_expiry(now: datetime | None = None) -> datetime:
    return (now or datetime.now(UTC)) + timedelta(days=SESSION_DAYS)
