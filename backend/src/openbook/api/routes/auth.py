"""회원가입·로그인·로그아웃.

- 응답의 token을 Authorization: Bearer <token>으로 보내면 로그인 상태다 (30일).
- 없는 이메일과 틀린 비밀번호는 같은 문구로 답한다 (가입 여부를 드러내지 않음).
- 같은 이메일로 다시 가입하면 409. 이메일은 앞뒤 공백을 빼고 소문자로 저장한다.
"""

from __future__ import annotations

import re
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from openbook.api.auth import (
    hash_password,
    new_token,
    session_expiry,
    token_hash,
    verify_password,
)
from openbook.api.deps import DB, UserId, api_error, current_session
from openbook.db import AuthSession, User

router = APIRouter(tags=["auth"])

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD = 8


class Credentials(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(max_length=128)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL.match(v):
            raise ValueError("이메일 형식을 확인해 주세요.")
        return v


class UserOut(BaseModel):
    id: str
    email: str


class LoginOut(BaseModel):
    token: str
    user: UserOut


def _issue(db: DB, user: User) -> LoginOut:
    token = new_token()
    db.add(AuthSession(token_hash=token_hash(token), user_id=user.id, expires_at=session_expiry()))
    db.commit()
    return LoginOut(token=token, user=UserOut(id=user.id, email=user.email))


def _by_email(db: DB, email: str) -> User | None:
    return db.scalars(select(User).where(User.email == email)).one_or_none()


@router.post("/auth/signup", response_model=LoginOut, status_code=201)
def signup(body: Credentials, db: DB) -> LoginOut:
    if len(body.password) < MIN_PASSWORD:
        raise api_error(422, "WEAK_PASSWORD", "비밀번호는 8자 이상으로 정해 주세요.")
    if _by_email(db, body.email) is not None:
        raise api_error(409, "EMAIL_TAKEN", "이미 가입한 이메일입니다. 로그인해 주세요.")
    user = User(email=body.email, password_hash=hash_password(body.password))
    db.add(user)
    db.flush()
    return _issue(db, user)


@router.post("/auth/login", response_model=LoginOut)
def login(body: Credentials, db: DB) -> LoginOut:
    user = _by_email(db, body.email)
    if not verify_password(body.password, user.password_hash if user else None) or user is None:
        raise api_error(401, "INVALID_CREDENTIALS", "이메일 또는 비밀번호가 맞지 않습니다.")
    return _issue(db, user)


@router.post("/auth/logout", status_code=204)
def logout(session: Annotated[AuthSession, Depends(current_session)], db: DB) -> Response:
    db.delete(session)
    db.commit()
    return Response(status_code=204)


@router.get("/auth/me", response_model=UserOut)
def me(user_id: UserId, db: DB) -> UserOut:
    user = db.get(User, user_id)
    if user is None:
        raise api_error(401, "UNAUTHENTICATED", "로그인이 필요합니다.")
    return UserOut(id=user.id, email=user.email)
