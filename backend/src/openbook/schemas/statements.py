"""정산서 입력 스키마 (명세서 2절 '정산서 입력', 5절 statements 테이블).

초안(v1): 팀 리뷰 후 확정한다.

원칙
- 정산서에 '적힌' 값만 담는다. 계약서 기준 금액은 계산 엔진(M5)이 따로 만든다.
- 금액은 terms.Money와 같은 규칙이다 (문자열·Decimal만 받고, JSON에서는 문자열).
- Statement는 사용자가 화면에서 확인한 값이다. StatementDraft는 붙여넣기를 읽은 초안이라
  빈칸이 있을 수 있고, 사용자가 고친 뒤 Statement로 보낸다.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator

from openbook.schemas.terms import Money, _blank


class StatementDeduction(BaseModel):
    """정산서에 적힌 공제 한 줄 (예: 앱마켓 수수료). 금액만 받는다."""

    name: str = Field(description="정산서에 적힌 공제 항목 이름")
    amount: Money

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, v: str) -> str:
        if _blank(v):
            raise ValueError("공제 항목 이름이 비어 있습니다.")
        return v


def _check_period(start: date | None, end: date | None) -> None:
    if start is not None and end is not None and end < start:
        raise ValueError("정산 기간의 끝이 시작보다 앞입니다.")


class Statement(BaseModel):
    """정산서 한 건 (statements 테이블 한 행). POST /contracts/{id}/statements 요청 본문."""

    period_start: date
    period_end: date
    gross: Money = Field(description="정산서에 적힌 총매출")
    deductions: list[StatementDeduction] = Field(
        default_factory=list, description="정산서에 적힌 공제 항목. 없으면 빈 목록"
    )
    reported_payout: Money = Field(description="정산서에 적힌 지급액")

    @model_validator(mode="after")
    def _period_order(self) -> Statement:
        _check_period(self.period_start, self.period_end)
        return self


class StatementField(StrEnum):
    PERIOD = "period"
    GROSS = "gross"
    DEDUCTION = "deduction"
    REPORTED_PAYOUT = "reported_payout"


class PastedRow(BaseModel):
    """붙여 넣은 표의 한 칸이 어디로 갔는지. 화면은 이것으로 '어느 줄에서 왔는지'를 보여 준다."""

    line: int = Field(description="붙여 넣은 글의 몇 번째 줄인가 (1부터)")
    label: str = Field(description="항목 이름 칸의 글자")
    value: str = Field(description="값 칸의 글자 (읽기 전 그대로)")
    field: StatementField | None = Field(
        default=None, description="어느 칸에 넣었는가. null이면 넣지 않음"
    )
    note: str | None = Field(default=None, description="넣지 않았거나 바꿔 넣은 이유")


class StatementDraft(BaseModel):
    """정산서 표 붙여넣기 결과 (초안). 빈칸은 사용자가 채운다."""

    period_start: date | None = None
    period_end: date | None = None
    gross: Money | None = None
    deductions: list[StatementDeduction] = Field(default_factory=list)
    reported_payout: Money | None = None
    rows: list[PastedRow] = Field(default_factory=list)
    missing: list[StatementField] = Field(
        default_factory=list, description="찾지 못한 칸 (period, gross, reported_payout 중)"
    )
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _period_order(self) -> StatementDraft:
        _check_period(self.period_start, self.period_end)
        return self
