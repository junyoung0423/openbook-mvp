"""M6 대조 결과 문장과 '플랫폼에 확인할 질문'.

문장은 템플릿이고 숫자는 엔진 출력을 문자열로 치환해 넣는다. LLM을 쓰지 않는다.
사용자가 입력한 이름(공제 항목 등)이 들어간 문장도 금지 표현 필터를 통과해야 나간다.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from openbook.engine import after_withholding, won
from openbook.safety import is_clean
from openbook.schemas.reconciliation import PeriodReconciliation
from openbook.schemas.terms import Deduction, MgRecoup

SUMMARY = "계약서 기준으로 계산하면 {computed}원, 정산서에는 {reported}원, 차이는 {diff}원입니다."
SUMMARY_UNSUPPORTED = "이 정산서는 계산하지 않았습니다. {reason}"
SUMMARY_TAX = (
    " 정산서 금액은 계약서 기준 금액에서 원천징수 3.3%를 뗀 {net}원과 거의 같습니다."
    " 세금을 뗀 뒤의 금액일 수 있습니다."
)
FALLBACK = "계산 결과는 아래 단계별 내역을 확인해 주세요."

Q_BREAKDOWN = "정산서 지급액이 어떤 순서로 계산되었는지 항목별 내역을 받을 수 있을까요?"
Q_UNKNOWN_DEDUCTION = (
    "정산서의 '{name}' 공제는 계약서의 어느 조항에 근거한 것인지 알려 주실 수 있을까요?"
)
Q_DEDUCTION_AMOUNT = (
    "'{name}' 공제가 정산서에는 {reported}원, 계약서 기준 계산으로는 {computed}원입니다. "
    "어떻게 계산되었는지 알려 주실 수 있을까요?"
)
Q_MG_BALANCE = "이 정산 기간 뒤 남은 MG(선급금) 금액을 알려 주실 수 있을까요?"
Q_TAX = "정산서 지급액이 원천징수 3.3%를 뗀 뒤의 금액인지 알려 주실 수 있을까요?"
Q_MISSING_PERIOD = "{start} ~ {end} 기간의 정산서를 보내 주실 수 있을까요?"
Q_GENERIC_DEDUCTION = "정산서의 공제 항목별 근거 조항을 알려 주실 수 있을까요?"


@dataclass(frozen=True)
class StatementLine:
    """정산서에 적힌 공제 한 줄."""

    name: str
    amount: Decimal


def _key(name: str) -> str:
    return "".join(name.split())


def _same_item(a: str, b: str) -> bool:
    ka, kb = _key(a), _key(b)
    return bool(ka and kb) and (ka in kb or kb in ka)


TAX_TOLERANCE = Decimal(10)


def withholding_match(r: PeriodReconciliation) -> Decimal | None:
    """R12: 정산서 지급액이 계약서 기준 금액에서 3.3%를 뗀 금액과 10원 안으로 같으면 그 금액."""
    if r.status != "computed" or r.computed_payout is None or r.computed_payout <= 0:
        return None
    if r.reported_payout >= r.computed_payout:
        return None
    net = after_withholding(r.computed_payout)
    return net if abs(r.reported_payout - net) <= TAX_TOLERANCE else None


def summary(r: PeriodReconciliation) -> str:
    if r.status == "unsupported":
        text = SUMMARY_UNSUPPORTED.format(reason=r.unsupported_reason or "")
    else:
        assert r.computed_payout is not None and r.diff is not None
        text = SUMMARY.format(
            computed=won(r.computed_payout), reported=won(r.reported_payout), diff=won(r.diff)
        )
        net = withholding_match(r)
        if net is not None:
            text += SUMMARY_TAX.format(net=won(net))
    return text if is_clean(text) else FALLBACK


def questions(
    r: PeriodReconciliation,
    statement_lines: Sequence[StatementLine],
    contract_deductions: Sequence[Deduction],
    recoup: MgRecoup,
    missing: tuple[date, date] | None = None,
) -> list[str]:
    out: list[str] = []
    if missing is not None:  # R11
        out.append(Q_MISSING_PERIOD.format(start=missing[0], end=missing[1]))
    if withholding_match(r) is not None:  # R12
        out.append(Q_TAX)
    if r.status == "unsupported" or (r.diff is not None and r.diff != 0):
        out.append(Q_BREAKDOWN)

    computed = {
        s.label.removeprefix("공제: "): s.value for s in r.breakdown if s.key == "deduction"
    }
    for line in statement_lines:
        match = next((d for d in contract_deductions if _same_item(d.name, line.name)), None)
        if match is None:
            out.append(Q_UNKNOWN_DEDUCTION.format(name=line.name))
        elif match.name in computed and computed[match.name] != line.amount:
            out.append(
                Q_DEDUCTION_AMOUNT.format(
                    name=line.name, reported=won(line.amount), computed=won(computed[match.name])
                )
            )

    if recoup is MgRecoup.FROM_RS:
        out.append(Q_MG_BALANCE)

    clean: list[str] = []
    for q in out:  # 사용자 입력 이름이 들어간 문장도 필터를 통과해야 한다
        q = q if is_clean(q) else Q_GENERIC_DEDUCTION
        if q not in clean:
            clean.append(q)
    return clean
