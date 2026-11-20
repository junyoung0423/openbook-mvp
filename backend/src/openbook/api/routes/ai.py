"""AI 모듈을 감싸는 엔드포인트 (정준영).

- GET  /contracts/{id}/comparison        표준계약서 비교 (M3, 정산 관련 핵심 조항)
- POST /contracts/{id}/qa                조항 Q&A (M7). 질문·답·인용 조항 id를 qa_logs에 남긴다
- POST /contracts/{id}/statements/paste  정산서 표 붙여넣기 읽기 (저장하지 않음, LLM 없음)

LLM 호출 실패는 502 LLM_FAILED로 알린다. 오류 문구에는 계약서 원문을 넣지 않는다.
"""

from __future__ import annotations

import hashlib
import json
import threading
from collections import OrderedDict
from functools import lru_cache

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator

from openbook.api.deps import DB, LLM, OwnedContract, api_error, require_clauses
from openbook.comparison import ComparisonResult, compare_with_standard, load_standard
from openbook.comparison.models import StandardClause
from openbook.db import QaLog
from openbook.qa import QAResult, answer_question
from openbook.schemas import Clause, StatementDraft
from openbook.statements import MAX_CHARS, parse_pasted_statement
from openbook.terms.llm import LLMError

router = APIRouter(tags=["ai"])

MAX_QUESTION = 500
_LLM_FAILED = "AI 호출에 실패했습니다. 잠시 후 다시 시도해 주세요."


def _llm_failed() -> Exception:
    return api_error(502, "LLM_FAILED", _LLM_FAILED)


# ---------------------------------------------------------------- comparison

# 비교는 LLM 호출이라 같은 조항이면 결과를 재사용한다. 서버 메모리라 재시작하면 사라진다.
# 결과를 DB에 둘지는 박다연 님과 정한다 (명세서 테이블에 없음).
_CACHE_SIZE = 256
_comparisons: OrderedDict[tuple[str, str], ComparisonResult] = OrderedDict()
_cache_lock = threading.Lock()


@lru_cache(maxsize=1)
def _core_standard() -> tuple[StandardClause, ...]:
    return tuple(load_standard(core_only=True))


@lru_cache(maxsize=1)
def _full_standard() -> tuple[StandardClause, ...]:
    return tuple(load_standard())


def _fingerprint(clauses: list[Clause]) -> str:
    raw = json.dumps([c.model_dump(mode="json") for c in clauses], ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


@router.get("/contracts/{contract_id}/comparison", response_model=ComparisonResult)
def get_comparison(
    contract: OwnedContract, db: DB, llm: LLM, refresh: bool = False
) -> ComparisonResult:
    clauses = require_clauses(db, contract.id)
    key = (contract.id, _fingerprint(clauses))
    with _cache_lock:  # 동기 엔드포인트는 스레드풀에서 돌므로 캐시를 잠근다
        if not refresh and key in _comparisons:
            _comparisons.move_to_end(key)
            return _comparisons[key]
    try:
        result = compare_with_standard(contract.id, clauses, list(_core_standard()), llm)
    except (LLMError, httpx.HTTPError):
        raise _llm_failed() from None
    with _cache_lock:
        _comparisons[key] = result
        while len(_comparisons) > _CACHE_SIZE:
            _comparisons.popitem(last=False)
    return result


# ---------------------------------------------------------------- Q&A


class QARequest(BaseModel):
    question: str = Field(min_length=1, max_length=MAX_QUESTION)

    @field_validator("question")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("질문이 비어 있습니다.")
        return v


@router.post("/contracts/{contract_id}/qa", response_model=QAResult)
def post_qa(body: QARequest, contract: OwnedContract, db: DB, llm: LLM) -> QAResult:
    clauses = require_clauses(db, contract.id)
    try:
        result = answer_question(contract.id, body.question, clauses, llm, list(_full_standard()))
    except (LLMError, httpx.HTTPError):
        raise _llm_failed() from None
    db.add(
        QaLog(
            contract_id=contract.id,
            question=result.question,
            answer=result.answer,
            cited_clause_ids=[c.clause_id for c in result.citations],
        )
    )
    db.commit()
    return result


# ---------------------------------------------------------------- statement paste


class PasteRequest(BaseModel):
    text: str = Field(max_length=MAX_CHARS, description="엑셀·웹 표를 복사해 붙여 넣은 글")


@router.post("/contracts/{contract_id}/statements/paste", response_model=StatementDraft)
def paste_statement(body: PasteRequest, contract: OwnedContract) -> StatementDraft:
    """붙여넣기를 읽어 정산서 입력 초안을 준다. 저장은 POST /contracts/{id}/statements가 한다."""
    return parse_pasted_statement(body.text)
