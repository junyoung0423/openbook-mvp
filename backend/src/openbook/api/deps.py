"""API 공통 의존성: DB 세션, 사용자, 계약서 소유 확인, LLM 클라이언트, 오류 형식.

오류 응답 본문은 {"detail": {"code": "...", "message": "..."}} 모양이다 (FastAPI HTTPException).
message에는 계약서 원문·정산서 값을 넣지 않는다.

테스트는 app.dependency_overrides로 get_db, get_llm을 바꿔 끼운다.
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from openbook.db import ClauseRecord, Contract, create_db_engine, make_session_factory
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


def get_llm() -> LLMClient:
    return UpstageClient.from_env()


def current_user_id(x_user_id: Annotated[str | None, Header()] = None) -> str:
    """임시 사용자 확인. 로그인(박다연 담당)이 붙으면 이 함수만 바꾼다.

    지금은 X-User-Id 헤더 값을 그대로 믿으므로 배포 전에 반드시 교체해야 한다.
    """
    if not x_user_id:
        raise api_error(401, "UNAUTHENTICATED", "로그인이 필요합니다.")
    return x_user_id


DB = Annotated[Session, Depends(get_db)]
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
