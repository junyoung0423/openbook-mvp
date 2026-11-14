"""계약서 텍스트 하나를 조항 목록과 MG·RS 조건으로 처리하는 묶음 함수 (M2 + M4).

API 서버(``POST /contracts`` 처리 작업)는 이 함수 하나만 부르면 된다.

    result = process_contract(contract_id, text, UpstageClient.from_env())

결과는 JSON으로 바로 저장·응답할 수 있다 (``result.model_dump(mode="json")``).
화면은 아래 값으로 다음 단계를 정한다.

- ``clause_review_needed``: 조항 분할이 불확실하다. 사용자가 나뉜 조항을 확인·수정하게 한다.
  조항을 하나도 못 나눴으면 ``clauses``가 비어 있고 조건 추출은 하지 않는다(``terms``가 null).
- ``error``: 조건 추출 호출이 실패했다. 조항 목록은 그대로 쓸 수 있고, 조건은 사용자가 직접 입력하거나
  다시 시도한다. 오류 문구에는 계약서 원문을 넣지 않는다.
- ``warnings``: 사용자가 확인해야 할 점(정해지지 않은 공제 항목, 바로잡은 근거 조항 번호 등).

계약서 원문은 로그에 남기지 않는다. 이 모듈은 아무것도 출력하지 않는다.
"""

from __future__ import annotations

import httpx
from pydantic import BaseModel, Field

from openbook.clauses import split_clauses
from openbook.schemas import Clause, TermSet
from openbook.terms import LLMClient, extract_terms
from openbook.terms.llm import LLMError


class ProcessResult(BaseModel):
    contract_id: str
    clause_style: str = Field(description="article(제N조) | numbered(N.) | none(규칙 실패)")
    clause_review_needed: bool = Field(description="조항 분할을 사용자가 확인해야 하면 true")
    clauses: list[Clause]
    terms: TermSet | None = Field(
        default=None, description="조건 9개 항목. 조항이 없거나 추출 호출이 실패하면 null"
    )
    warnings: list[str] = Field(default_factory=list)
    error: str | None = Field(default=None, description="조건 추출 호출 실패 사유")


def process_contract(contract_id: str, text: str, llm: LLMClient) -> ProcessResult:
    split = split_clauses(text)
    warnings = list(split.warnings)
    result = ProcessResult(
        contract_id=contract_id,
        clause_style=split.style,
        clause_review_needed=split.needs_llm,
        clauses=split.clauses,
        warnings=warnings,
    )
    if not split.clauses:
        return result  # 나뉜 조항이 없으면 조건을 뽑을 근거 문장도 없다

    try:
        extraction = extract_terms(contract_id, split.clauses, llm)
    except (LLMError, httpx.HTTPError) as exc:
        result.error = f"조건 추출 호출에 실패했습니다: {exc}"
        return result

    result.terms = extraction.terms
    result.warnings = warnings + extraction.warnings
    return result
