"""MG·RS 조건 스키마 (M4 출력, 명세서 4절 표·5절 terms 테이블).

초안(v1): 팀 리뷰 후 확정한다. 선택값 목록(enum)은 명세서에 값이 정해져 있지 않은 부분은
초안이며, 허정민 님의 계약 유형 분류 결과로 확정한다.

원칙
- 금액·비율은 Decimal이며 JSON에서는 문자열로 직렬화된다 (float 오차 방지).
- 모든 추출값은 근거 조항(source_clause_id)과 원문 인용(quote)을 가진다.
- 못 찾으면 status='not_found', value=None.
- confirmed=True는 사용자만 만든다. 확정된 값만 계산 엔진에 들어간다.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, Field, TypeAdapter, model_validator

# ---------------------------------------------------------------- enums


class TermKey(StrEnum):
    MG_AMOUNT = "mg_amount"
    MG_PAY_DATE = "mg_pay_date"
    MG_RECOUP = "mg_recoup"
    MG_CARRYOVER = "mg_carryover"
    RS_RATE = "rs_rate"
    REVENUE_BASE = "revenue_base"
    DEDUCTIONS = "deductions"
    SETTLEMENT_CYCLE = "settlement_cycle"
    PAYMENT_DAY = "payment_day"


class TermStatus(StrEnum):
    EXTRACTED = "extracted"  # 추출됨
    NOT_FOUND = "not_found"  # 찾지 못함 (표준과 같다는 뜻이 아님)
    USER_INPUT = "user_input"  # 직접 입력


class MgRecoup(StrEnum):
    FROM_RS = "from_rs"  # RS에서 차감
    SEPARATE = "separate"  # 별도
    UNKNOWN = "unknown"  # 불명


class MgCarryover(StrEnum):
    CARRY_OVER = "carry_over"  # 미회수분 이월
    REFUND = "refund"  # 환수
    FORGIVEN = "forgiven"  # 소멸
    UNKNOWN = "unknown"


class RevenueBase(StrEnum):
    GROSS = "gross"  # 총매출
    NET = "net"  # 순매출
    OTHER = "other"  # 기타 (원문 확인 필요)


class SettlementCycle(StrEnum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMIANNUAL = "semiannual"
    OTHER = "other"


# ---------------------------------------------------------------- value shapes

Money = Annotated[Decimal, Field(ge=0, description="원 단위 금액")]
Rate = Annotated[Decimal, Field(ge=0, le=1, description="비율. 0.6 = 60%")]


class RsTier(BaseModel):
    """구간별 RS. MVP 계산은 지원하지 않지만 스키마에는 둔다 (명세서 M5)."""

    from_amount: Money = Decimal(0)
    to_amount: Money | None = Field(default=None, description="null이면 상한 없음")
    rate: Rate


class Deduction(BaseModel):
    name: str
    rate: Rate | None = None
    amount: Money | None = None

    @model_validator(mode="after")
    def _rate_xor_amount(self) -> Deduction:
        if (self.rate is None) == (self.amount is None):
            raise ValueError("공제 항목은 rate 또는 amount 중 정확히 하나만 가져야 합니다.")
        return self


# key -> value를 검증하는 타입. 날짜·지급 시기는 문구가 올 수 있어 str로 둔다.
_VALUE_TYPES: dict[TermKey, Any] = {
    TermKey.MG_AMOUNT: Money,
    TermKey.MG_PAY_DATE: str,
    TermKey.MG_RECOUP: MgRecoup,
    TermKey.MG_CARRYOVER: MgCarryover,
    TermKey.RS_RATE: Rate | list[RsTier],
    TermKey.REVENUE_BASE: RevenueBase,
    TermKey.DEDUCTIONS: list[Deduction],
    TermKey.SETTLEMENT_CYCLE: SettlementCycle,
    TermKey.PAYMENT_DAY: str,
}
_ADAPTERS = {k: TypeAdapter(t) for k, t in _VALUE_TYPES.items()}


# ---------------------------------------------------------------- term


class Term(BaseModel):
    """조건 한 항목 (terms 테이블 한 행)."""

    key: TermKey
    value: Any = Field(
        default=None, description="key별 형식. JSON Schema에서는 Term의 oneOf에 key별로 적혀 있다."
    )
    status: TermStatus
    source_clause_id: str | None = Field(default=None, description="근거 조항 id")
    quote: str | None = Field(default=None, description="근거 조항 원문 인용 (그대로)")
    confirmed: bool = False
    confirmed_at: datetime | None = None

    @model_validator(mode="after")
    def _check(self) -> Term:
        if self.status is TermStatus.NOT_FOUND:
            if self.value is not None:
                raise ValueError("not_found인 조건은 value가 null이어야 합니다.")
            if self.confirmed:
                raise ValueError("찾지 못한 조건은 값을 입력하기 전에는 확정할 수 없습니다.")
        else:
            if self.value is None:
                raise ValueError(f"status={self.status.value}이면 value가 필요합니다.")
            # 형식 검증 후 정규화된 값으로 교체 (Decimal, enum 등)
            self.value = _ADAPTERS[self.key].validate_python(self.value)

        if self.status is TermStatus.EXTRACTED and not (self.source_clause_id and self.quote):
            raise ValueError(
                "추출된 값에는 근거 조항 id(source_clause_id)와 원문 인용(quote)이 필요합니다."
            )

        if self.confirmed and self.confirmed_at is None:
            raise ValueError("confirmed=true이면 confirmed_at이 필요합니다.")
        return self


class TermSet(BaseModel):
    """GET, PUT /contracts/{id}/terms 본문. 같은 key는 한 번만 둔다."""

    contract_id: str
    terms: list[Term]

    @model_validator(mode="after")
    def _unique_keys(self) -> TermSet:
        keys = [t.key for t in self.terms]
        if len(keys) != len(set(keys)):
            raise ValueError("같은 key의 조건이 중복되었습니다.")
        return self

    @property
    def all_confirmed(self) -> bool:
        """계산·대조는 모든 필요한 조건이 확정된 뒤에만 실행한다."""
        return bool(self.terms) and all(t.confirmed for t in self.terms)


# ---------------------------------------------------------------- JSON Schema


def termset_json_schema() -> dict[str, Any]:
    """TermSet의 JSON Schema. Term.value의 key별 형식과 선택값을 oneOf로 드러낸다.

    런타임 검증은 Term._check가 하고, 이 함수는 프론트엔드 타입 생성용 문서만 만든다.
    금액·비율은 응답과 같은 모양(문자열)으로 적는다 (serialization 모드).
    """
    schema = TermSet.model_json_schema(mode="serialization")
    defs = schema.setdefault("$defs", {})
    variants = []
    for key, value_type in _VALUE_TYPES.items():
        value_schema = TypeAdapter(value_type | None).json_schema(
            mode="serialization", ref_template="#/$defs/{model}"
        )
        defs.update(value_schema.pop("$defs", {}))
        variants.append(
            {
                "properties": {"key": {"const": key.value}, "value": value_schema},
                "required": ["key"],
            }
        )
    defs["Term"]["oneOf"] = variants
    return schema
