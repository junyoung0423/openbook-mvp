"""MG·RS 조건 스키마 (M4 출력, 명세서 4절 표·5절 terms 테이블).

초안(v1): 팀 리뷰 후 확정한다. 선택값 목록(enum)은 명세서에 값이 정해져 있지 않은 부분은
초안이며, 허정민 님의 계약 유형 분류 결과로 확정한다.

원칙
- 금액·비율은 Decimal이며 JSON에서는 문자열로 직렬화된다 (float 오차 방지).
- 모든 추출값은 근거 조항(source_clause_id)과 원문 인용(quote)을 가진다.
- 못 찾으면 status='not_found', value=None.
- confirmed=True는 사용자만 만든다. 확정된 값만 계산 엔진에 들어간다.
- 계산에 꼭 필요한 조건은 REQUIRED_TERM_KEYS 5개다 (이슈 #1 리뷰에서 허정민 님이 정함).
  나머지 4개는 '찾지 못함'이어도 대조가 열린다.
- JSON Schema로 표현되지 않는 상태 규칙(not_found면 value가 null 등)은 서버가 검증한다.
"""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    Field,
    PlainSerializer,
    TypeAdapter,
    WithJsonSchema,
    field_serializer,
    field_validator,
    model_validator,
)

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

# \d는 전각 숫자("５００")도 받으므로 [0-9]로 쓴다 (JSON Schema 정규식과 같은 뜻이 되게)
MONEY_PATTERN = r"^[0-9]+(\.[0-9]+)?$"
SIGNED_MONEY_PATTERN = r"^-?[0-9]+(\.[0-9]+)?$"  # 정산서 매출·정산액 (환불이 많은 달은 음수)
RATE_PATTERN = r"^(0(\.[0-9]+)?|1(\.0+)?)$"


def _decimal_text(pattern: str):
    """금액·비율 입력 검사. 문자열(숫자·소수점 모양)이나 Decimal만 받는다.

    float·JSON 숫자는 오차가 생길 수 있어 거절하고, "1e7" 같은 지수 표기도 거절한다.
    """
    rx = re.compile(pattern)

    def check(v: Any) -> Any:
        if isinstance(v, Decimal):
            if not v.is_finite():
                raise ValueError("금액·비율에 무한대·NaN은 쓸 수 없습니다.")
            return v
        # pydantic은 ValueError만 검증 오류로 바꾸므로 TypeError 대신 ValueError를 쓴다
        if not isinstance(v, str):
            raise ValueError('금액·비율은 문자열로 보내야 합니다. 예: "5000000", "0.6"')  # noqa: TRY004
        if not rx.fullmatch(v):
            raise ValueError(f"금액·비율 형식이 아닙니다: {v!r}")
        return v

    return BeforeValidator(check)


# JSON에는 지수 표기 없이 고정 소수점 문자열로 내보낸다 (Decimal("1E+7") -> "10000000")
_AS_PLAIN_TEXT = PlainSerializer(lambda d: format(d, "f"), return_type=str, when_used="json")

Money = Annotated[
    Decimal,
    _decimal_text(MONEY_PATTERN),
    Field(ge=0),
    _AS_PLAIN_TEXT,
    WithJsonSchema({"type": "string", "pattern": MONEY_PATTERN, "description": "원 단위 금액"}),
]
SignedMoney = Annotated[
    Decimal,
    _decimal_text(SIGNED_MONEY_PATTERN),
    _AS_PLAIN_TEXT,
    WithJsonSchema(
        {
            "type": "string",
            "pattern": SIGNED_MONEY_PATTERN,
            "description": "원 단위 금액 (음수 가능)",
        }
    ),
]
Rate = Annotated[
    Decimal,
    _decimal_text(RATE_PATTERN),
    Field(ge=0, le=1),
    _AS_PLAIN_TEXT,
    WithJsonSchema({"type": "string", "pattern": RATE_PATTERN, "description": '비율. "0.6" = 60%'}),
]


def _blank(s: str | None) -> bool:
    return s is None or not s.strip()


def _not_blank_text(v: str) -> str:
    if _blank(v):
        raise ValueError("빈 문구는 쓸 수 없습니다. 못 찾았으면 status를 not_found로 두세요.")
    return v


# 날짜·지급 시기처럼 계약서 문구를 그대로 담는 값. 공백뿐인 문자열은 거절한다.
ContractText = Annotated[
    str,
    AfterValidator(_not_blank_text),
    WithJsonSchema({"type": "string", "pattern": r"\S", "description": "계약서 문구 그대로"}),
]


class RsTier(BaseModel):
    """구간별 RS. MVP 계산은 지원하지 않지만 스키마에는 둔다 (명세서 M5)."""

    from_amount: Money = Decimal(0)
    to_amount: Money | None = Field(default=None, description="null이면 상한 없음")
    rate: Rate


class Deduction(BaseModel):
    name: str
    rate: Rate | None = None
    amount: Money | None = None

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, v: str) -> str:
        if _blank(v):
            raise ValueError("공제 항목 이름이 비어 있습니다.")
        return v

    @model_validator(mode="after")
    def _rate_xor_amount(self) -> Deduction:
        if (self.rate is None) == (self.amount is None):
            raise ValueError("공제 항목은 rate 또는 amount 중 정확히 하나만 가져야 합니다.")
        return self


# key -> value를 검증하는 타입. 날짜·지급 시기는 문구가 올 수 있어 str로 둔다.
_VALUE_TYPES: dict[TermKey, Any] = {
    TermKey.MG_AMOUNT: Money,
    TermKey.MG_PAY_DATE: ContractText,
    TermKey.MG_RECOUP: MgRecoup,
    TermKey.MG_CARRYOVER: MgCarryover,
    TermKey.RS_RATE: Rate | Annotated[list[RsTier], Field(min_length=1)],
    TermKey.REVENUE_BASE: RevenueBase,
    TermKey.DEDUCTIONS: list[Deduction],
    TermKey.SETTLEMENT_CYCLE: SettlementCycle,
    TermKey.PAYMENT_DAY: ContractText,
}
_ADAPTERS = {k: TypeAdapter(t) for k, t in _VALUE_TYPES.items()}

# 계산에 꼭 필요한 조건. 이 5개가 모두 확정되어야 계산·대조를 연다.
REQUIRED_TERM_KEYS: tuple[TermKey, ...] = (
    TermKey.MG_AMOUNT,
    TermKey.MG_RECOUP,
    TermKey.RS_RATE,
    TermKey.REVENUE_BASE,
    TermKey.DEDUCTIONS,
)


# ---------------------------------------------------------------- term


class Term(BaseModel):
    """조건 한 항목 (terms 테이블 한 행)."""

    key: TermKey
    value: Any = Field(
        default=None, description="key별 형식. JSON Schema에서는 Term의 oneOf에 key별로 적혀 있다."
    )
    status: TermStatus = Field(
        description=(
            "extracted=추출됨, not_found=찾지 못함(표준·일반 조건과 같다는 뜻이 아님), "
            "user_input=직접 입력"
        )
    )
    source_clause_id: str | None = Field(default=None, description="근거 조항 id")
    quote: str | None = Field(default=None, description="근거 조항 원문 인용 (그대로)")
    confirmed: bool = False
    confirmed_at: datetime | None = None

    @field_serializer("value", when_used="json")
    def _dump_value(self, v: Any) -> Any:
        # value는 Any라서 key별 타입의 직렬화(금액을 고정 소수점 문자열로)를 직접 적용한다
        return None if v is None else _ADAPTERS[self.key].dump_python(v, mode="json")

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

        if self.status is TermStatus.EXTRACTED and (
            _blank(self.source_clause_id) or _blank(self.quote)
        ):
            raise ValueError(
                "추출된 값에는 근거 조항 id(source_clause_id)와 원문 인용(quote)이 필요합니다."
            )

        if self.confirmed and self.confirmed_at is None:
            raise ValueError("confirmed=true이면 confirmed_at이 필요합니다.")
        if not self.confirmed and self.confirmed_at is not None:
            raise ValueError("확정하지 않은 조건에는 confirmed_at이 없어야 합니다.")
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
    def missing_keys(self) -> list[TermKey]:
        """목록에 아예 없는 key. M4는 9개 key를 모두 (찾지 못함 포함) 돌려준다."""
        have = {t.key for t in self.terms}
        return [k for k in TermKey if k not in have]

    @property
    def unconfirmed_required(self) -> list[TermKey]:
        """아직 확정되지 않은 필수 조건 (화면에서 '이 항목을 확인해 주세요'에 쓴다)."""
        confirmed = {t.key for t in self.terms if t.confirmed}
        return [k for k in REQUIRED_TERM_KEYS if k not in confirmed]

    @property
    def all_confirmed(self) -> bool:
        """계산·대조를 열 수 있는가: 9개 key가 모두 있고 필수 5개가 모두 확정됨.

        필수가 아닌 4개는 찾지 못함·미확정이어도 된다.
        """
        return not self.missing_keys and not self.unconfirmed_required


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
