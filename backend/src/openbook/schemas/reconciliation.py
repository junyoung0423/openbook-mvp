"""대조 결과 스키마 (GET /contracts/{id}/reconciliations 응답).

금액은 Decimal이고 JSON에서는 문자열로 나간다. 차이(diff)는 음수일 수 있다.
차이 = 계약서 기준 금액 − 정산서 금액 (명세서). 부호를 바꾸지 않는다.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from openbook.schemas.terms import TermKey

DIFF_MEANING = "차이는 계약서 기준 금액에서 정산서 금액을 뺀 값입니다."
RESULT_NOTICE = (
    "이 결과는 사용자가 확정한 조건으로 계산한 것입니다. 법률·세무 자문이 아닙니다. "
    "계약서 문구의 해석이 필요하면 전문가와 상담해 주세요."
)


class CalcStep(BaseModel):
    """계산 한 단계. 대조 화면이 이 목록을 그대로 보여 준다."""

    key: Literal["deduction", "base", "rs_share", "mg_before", "payout", "mg_after", "diff"]
    label: str
    value: Decimal
    formula: str | None = Field(default=None, description="숫자는 코드가 넣는다")
    term_key: TermKey | None = None
    source_clause_id: str | None = Field(default=None, description="근거 조항 id")


class PeriodReconciliation(BaseModel):
    """정산서 한 건의 대조 결과."""

    statement_id: str
    period_start: date
    period_end: date
    status: Literal["computed", "unsupported"]
    computed_payout: Decimal | None = Field(default=None, description="계약서 기준 지급액")
    reported_payout: Decimal = Field(description="정산서에 적힌 지급액")
    diff: Decimal | None = Field(default=None, description="계약서 기준 − 정산서")
    mg_balance_after: Decimal | None = Field(
        default=None, description="이 기간 뒤 남은 MG. RS에서 회수하지 않는 계약이면 null"
    )
    breakdown: list[CalcStep] = Field(default_factory=list)
    unsupported_reason: str | None = None
    summary: str = Field(default="", description="결과 문장 (템플릿, 숫자는 치환)")
    questions: list[str] = Field(default_factory=list, description="플랫폼에 확인할 질문")


class ReconciliationReport(BaseModel):
    contract_id: str
    items: list[PeriodReconciliation]
    rules_version: str = Field(description="계산 규칙 버전. 임시 안이면 'provisional-…'")
    diff_meaning: str = DIFF_MEANING
    notice: str = RESULT_NOTICE
