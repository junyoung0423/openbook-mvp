"""대조 결과 스키마 (GET /contracts/{id}/reconciliations 응답). 계산 규칙은 engine/rules.py (R1–R12).

금액은 Decimal이고 JSON에서는 문자열로 나간다. 차이는 음수일 수 있다.
차이 = 정산서 값 − 계약서 기준 계산 값 (검산표 기준). 음수면 정산서가 계산보다 적다.
정산서 한 건에서 세 칸을 대조한다: 정산액(R12), 원천징수(R11), 작가지급액(R7).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from openbook.schemas.terms import TermKey

DIFF_MEANING = (
    "차이는 정산서에 적힌 금액에서 계약서 기준으로 계산한 금액을 뺀 값입니다. "
    "음수면 정산서 금액이 계산보다 적습니다."
)
RESULT_NOTICE = (
    "이 결과는 사용자가 확정한 조건으로 계산한 것입니다. 법률·세무 자문이 아닙니다. "
    "계약서 문구의 해석이 필요하면 전문가와 상담해 주세요."
)

StepKey = Literal[
    "revenue",
    "deduction",
    "base",
    "rs_share",
    "mg_before",
    "payout",
    "mg_after",
    "income_tax",
    "local_tax",
    "net_payout",
    "diff_settlement",
    "diff_withholding",
    "diff",
]


class CalcStep(BaseModel):
    """계산 한 단계. 대조 화면이 이 목록을 그대로 보여 준다. value는 원 미만까지 정확한 값일 수 있다."""

    key: StepKey
    label: str
    value: Decimal
    formula: str | None = Field(default=None, description="숫자는 코드가 넣는다")
    term_key: TermKey | None = None
    source_clause_id: str | None = Field(default=None, description="근거 조항 id")


class PeriodReconciliation(BaseModel):
    """정산서 한 건의 대조 결과. status=unsupported면 금액 칸은 모두 null이다 (R10)."""

    statement_id: str
    period_start: date
    period_end: date
    status: Literal["computed", "unsupported"]

    computed_settlement: Decimal | None = Field(
        default=None, description="작가 몫 S (원 미만 버림). 정산서 '정산액'과 비교 (R12)"
    )
    reported_settlement: Decimal | None = Field(default=None, description="정산서 '정산액'")
    settlement_diff: Decimal | None = Field(default=None, description="정산서 − 계산")

    payout_before_tax: Decimal | None = Field(default=None, description="지급액 P (세전)")
    computed_withholding: Decimal | None = Field(default=None, description="원천징수 (R11)")
    reported_withholding: Decimal | None = Field(default=None, description="정산서 '원천징수'")
    withholding_diff: Decimal | None = Field(default=None, description="정산서 − 계산")

    computed_payout: Decimal | None = Field(
        default=None, description="실지급액 = P − 원천징수. 정산서 '작가지급액'과 비교 (R7)"
    )
    reported_payout: Decimal = Field(description="정산서 '작가지급액'")
    diff: Decimal | None = Field(default=None, description="작가지급액: 정산서 − 계산")

    mg_balance_after: Decimal | None = Field(
        default=None, description="이 기간 뒤 남은 MG (원 미만 버림 표시). 별도 계약이면 null"
    )
    breakdown: list[CalcStep] = Field(default_factory=list)
    unsupported_reason: str | None = None
    summary: str = Field(default="", description="결과 문장 (템플릿, 숫자는 치환)")
    questions: list[str] = Field(default_factory=list, description="플랫폼에 확인할 질문")


class ReconciliationReport(BaseModel):
    contract_id: str
    items: list[PeriodReconciliation]
    rules_version: str = Field(description="계산 규칙 버전")
    unsupported_reason: str | None = Field(
        default=None,
        description="계약 전체를 계산하지 않은 이유 (R10). 있으면 금액을 보이지 않는다",
    )
    diff_meaning: str = DIFF_MEANING
    notice: str = RESULT_NOTICE
