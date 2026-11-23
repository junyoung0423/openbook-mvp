"""계약서 업로드·조회·삭제 (명세서 5절 P0).

- 업로드는 파일(POST /contracts) 또는 본문 붙여넣기(POST /contracts/text)로 받는다.
- 처리(파싱 → process_contract → 저장)는 응답을 보낸 뒤 돈다. 화면은 GET /contracts/{id}의
  status로 끝났는지 확인한다: 처리중 → 조건 확인 대기 / 처리 실패.
- 원본 파일은 저장하지 않는다 (file_ref 비움). 처리에 쓴 뒤 버린다.
- 오류 문구에는 계약서 원문을 넣지 않는다.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from openbook.api.deps import (
    DB,
    LLM,
    OwnedContract,
    UserId,
    api_error,
    get_parser,
    get_session_factory,
    load_clauses,
)
from openbook.api.process_store import save_process_result
from openbook.db import Contract, User
from openbook.parsing import UpstageDocumentParser, parse_pasted_text
from openbook.parsing.upstage import SUPPORTED_EXTENSIONS
from openbook.pipeline import process_contract
from openbook.schemas import Clause
from openbook.terms import LLMClient

log = logging.getLogger(__name__)
router = APIRouter(tags=["contracts"])

MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_TEXT_CHARS = 100_000
STATUS_PROCESSING = "처리중"
STATUS_FAILED = "처리 실패"

Sessions = Annotated[sessionmaker[Session], Depends(get_session_factory)]
Parser = Annotated[UpstageDocumentParser, Depends(get_parser)]


class ContractOut(BaseModel):
    id: str
    title: str
    status: str = Field(description="처리중 / 조건 확인 대기 / 확정 / 처리 실패")
    uploaded_at: datetime

    @classmethod
    def of(cls, c: Contract) -> ContractOut:
        return cls(id=c.id, title=c.title, status=c.status, uploaded_at=c.uploaded_at)


class ContractText(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    text: str = Field(min_length=1, max_length=MAX_TEXT_CHARS)


def _ensure_user(db: Session, user_id: str) -> None:
    """임시: 로그인이 붙기 전에는 X-User-Id로 사용자 행을 만든다."""
    if db.get(User, user_id) is None:
        db.add(User(id=user_id, email=f"{user_id}@users.invalid"))
        db.flush()


def _create(db: Session, user_id: str, title: str) -> Contract:
    _ensure_user(db, user_id)
    contract = Contract(user_id=user_id, title=title.strip(), status=STATUS_PROCESSING)
    db.add(contract)
    db.commit()
    return contract


def _fail(sessions: sessionmaker[Session], contract_id: str) -> None:
    with sessions.begin() as s:
        c = s.get(Contract, contract_id)
        if c is not None:
            c.status = STATUS_FAILED


def run_processing(
    sessions: sessionmaker[Session],
    contract_id: str,
    llm: LLMClient,
    *,
    text: str | None = None,
    file: tuple[str, bytes] | None = None,
    parser: UpstageDocumentParser | None = None,
) -> None:
    """파싱 → process_contract → 저장. 실패하면 상태만 '처리 실패'로 둔다 (원문은 남기지 않음)."""
    try:
        if file is not None:
            assert parser is not None
            text = parser.parse_file(*file).text
        result = process_contract(contract_id, text or "", llm)
    except Exception as exc:  # noqa: BLE001 — 어떤 실패든 상태로 알린다. 로그에는 예외 종류만
        log.warning("contract processing failed: %s", type(exc).__name__)
        _fail(sessions, contract_id)
        return
    with sessions.begin() as s:
        c = s.get(Contract, contract_id)
        if c is None:  # 처리 중에 삭제됨
            return
        save_process_result(s, c, result)
        if not result.clauses:
            c.status = STATUS_FAILED


@router.post("/contracts", response_model=ContractOut, status_code=202)
async def upload_contract(
    background: BackgroundTasks,
    db: DB,
    user_id: UserId,
    llm: LLM,
    parser: Parser,
    sessions: Sessions,
    file: Annotated[UploadFile, File()],
    title: Annotated[str | None, Form(max_length=255)] = None,
) -> ContractOut:
    name = file.filename or ""
    if Path(name).suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise api_error(415, "UNSUPPORTED_FILE", "지원하지 않는 파일 형식입니다.")
    content = await file.read(MAX_FILE_BYTES + 1)
    if not content:
        raise api_error(422, "EMPTY_FILE", "빈 파일입니다.")
    if len(content) > MAX_FILE_BYTES:
        raise api_error(413, "FILE_TOO_LARGE", "파일은 20MB까지 올릴 수 있습니다.")
    contract = _create(db, user_id, title or Path(name).stem or "계약서")
    background.add_task(
        run_processing, sessions, contract.id, llm, file=(name, content), parser=parser
    )
    return ContractOut.of(contract)


@router.post("/contracts/text", response_model=ContractOut, status_code=202)
def upload_contract_text(
    body: ContractText,
    background: BackgroundTasks,
    db: DB,
    user_id: UserId,
    llm: LLM,
    sessions: Sessions,
) -> ContractOut:
    if not body.text.strip() or not body.title.strip():
        raise api_error(422, "EMPTY_TEXT", "계약서 본문과 제목을 입력해 주세요.")
    text = parse_pasted_text(body.text).text
    contract = _create(db, user_id, body.title)
    background.add_task(run_processing, sessions, contract.id, llm, text=text)
    return ContractOut.of(contract)


@router.get("/contracts", response_model=list[ContractOut])
def list_contracts(db: DB, user_id: UserId) -> list[ContractOut]:
    rows = db.scalars(
        select(Contract).where(Contract.user_id == user_id).order_by(Contract.uploaded_at.desc())
    ).all()
    return [ContractOut.of(c) for c in rows]


@router.get("/contracts/{contract_id}", response_model=ContractOut)
def get_contract(contract: OwnedContract) -> ContractOut:
    return ContractOut.of(contract)


@router.get("/contracts/{contract_id}/clauses", response_model=list[Clause])
def get_clauses(contract: OwnedContract, db: DB) -> list[Clause]:
    return load_clauses(db, contract.id)


@router.delete("/contracts/{contract_id}", status_code=204)
def delete_contract(contract: OwnedContract, db: DB) -> Response:
    """계약서와 조항·조건·정산서·대조 결과·Q&A 기록을 함께 지운다."""
    db.delete(contract)
    db.commit()
    return Response(status_code=204)
