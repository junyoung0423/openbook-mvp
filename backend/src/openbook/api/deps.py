"""API 공통 의존성: DB 세션, 사용자, 계약서 소유 확인, LLM 클라이언트, 오류 형식.

오류 응답 본문은 {"detail": {"code": "...", "message": "..."}} 모양이다 (FastAPI HTTPException).
message에는 계약서 원문·정산서 값을 넣지 않는다.

테스트는 app.dependency_overrides로 get_db, get_llm을 바꿔 끼운다.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated

from dotenv import dotenv_values
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from openbook.api.auth import token_hash
from openbook.db import (
    AuthSession,
    ClauseRecord,
    Contract,
    User,
    create_db_engine,
    make_session_factory,
)
from openbook.parsing import DocumentParseConfigError, UpstageDocumentParser
from openbook.schemas import Clause
from openbook.terms import LLMClient, UpstageClient


def api_error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


@lru_cache(maxsize=1)
def _sessions() -> sessionmaker[Session]:
    return make_session_factory(create_db_engine())  # DATABASE_URL, 없으면 로컬 SQLite


def get_db() -> Iterator[Session]:
    with _sessions()() as session:
        yield session


def get_session_factory() -> sessionmaker[Session]:
    """요청이 끝난 뒤 도는 작업(계약서 처리)이 쓰는 세션 공장."""
    return _sessions()


def get_parser() -> UpstageDocumentParser:
    try:
        return UpstageDocumentParser.from_env()
    except DocumentParseConfigError:
        raise api_error(503, "LLM_NOT_CONFIGURED", "AI 기능이 아직 설정되지 않았습니다.") from None


def get_llm() -> LLMClient:
    try:
        return UpstageClient.from_env()
    except ValueError:  # API 키가 비어 있음. 키 값은 문구에 넣지 않는다
        raise api_error(503, "LLM_NOT_CONFIGURED", "AI 기능이 아직 설정되지 않았습니다.") from None


DB = Annotated[Session, Depends(get_db)]


def _bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return None
    return token.strip() or None


def current_session(db: DB, authorization: Annotated[str | None, Header()] = None) -> AuthSession:
    """Authorization: Bearer <토큰>으로 로그인 세션을 찾는다. 없거나 만료면 401."""
    token = _bearer(authorization)
    row = db.get(AuthSession, token_hash(token)) if token else None
    if row is not None:
        expires = row.expires_at
        if expires.tzinfo is None:  # SQLite는 시간대 없이 돌려준다 (저장은 UTC)
            expires = expires.replace(tzinfo=UTC)
        if expires > datetime.now(UTC):
            return row
    raise api_error(401, "UNAUTHENTICATED", "로그인이 필요합니다.")


AUTH_OFF_FLAG = "OPENBOOK_AUTH_DISABLED"
LOCAL_USER_ID = "local-user"
LOCAL_USER_EMAIL = "local@openbook.invalid"


def auth_disabled(db: Session) -> bool:
    """로컬 개발용: OPENBOOK_AUTH_DISABLED=1이고 SQLite DB일 때만 로그인을 끈다.

    배포 DB(Postgres)에서는 이 값이 있어도 로그인을 끄지 않는다. .env 전체를 불러오지 않고
    이 값만 읽는다 (.env의 DATABASE_URL이 실행 중에 바뀌지 않게).
    """
    flag = os.getenv(AUTH_OFF_FLAG) or dotenv_values().get(AUTH_OFF_FLAG)
    return flag == "1" and db.get_bind().url.get_backend_name() == "sqlite"


def current_user_id(db: DB, authorization: Annotated[str | None, Header()] = None) -> str:
    if auth_disabled(db):
        if db.get(User, LOCAL_USER_ID) is None:
            db.add(User(id=LOCAL_USER_ID, email=LOCAL_USER_EMAIL))
            db.commit()
        return LOCAL_USER_ID
    return current_session(db, authorization).user_id


UserId = Annotated[str, Depends(current_user_id)]
LLM = Annotated[LLMClient, Depends(get_llm)]


def owned_contract(contract_id: str, db: DB, user_id: UserId) -> Contract:
    """내 계약서만 연다. 남의 계약서도 '없음'으로 답해 존재 여부를 드러내지 않는다."""
    contract = db.get(Contract, contract_id)
    if contract is None or contract.user_id != user_id:
        raise api_error(404, "CONTRACT_NOT_FOUND", "계약서를 찾을 수 없습니다.")
    return contract


OwnedContract = Annotated[Contract, Depends(owned_contract)]


def load_clauses(db: Session, contract_id: str) -> list[Clause]:
    """저장된 조항을 계약서 순서(id 순, 예: c-01, c-02)로."""
    rows = db.scalars(select(ClauseRecord).where(ClauseRecord.contract_id == contract_id)).all()
    return [
        Clause(id=r.id, no=r.no, title=r.title, text=r.text)
        for r in sorted(rows, key=lambda r: r.id)
    ]


def require_clauses(db: Session, contract_id: str) -> list[Clause]:
    clauses = load_clauses(db, contract_id)
    if not clauses:
        raise api_error(
            409, "NO_CLAUSES", "조항이 아직 없습니다. 계약서 처리가 끝난 뒤 다시 시도하세요."
        )
    return clauses
