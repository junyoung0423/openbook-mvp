"""M5 계산 엔진. 순수 함수, Decimal만 쓴다. 규칙은 engine/rules.py (R1–R12).

LLM·파일·네트워크·시간·난수를 쓰지 않는다. 입력은 사용자가 확정한 조건과 정산서 값뿐이다.
필수 조건이 비어 있으면 계산 불가(R10), 값은 있는데 확정되지 않았으면 ValueError.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_DOWN, Decimal
from itertools import pairwise

from openbook.engine import rules
from openbook.schemas.reconciliation import CalcStep, PeriodReconciliation
from openbook.schemas.terms import (
    REQUIRED_TERM_KEYS,
    Deduction,
    MgRecoup,
    RevenueBase,
    Term,
    TermKey,
)

ZERO = Decimal(0)


@dataclass(frozen=True)
class StatementInput:
    """정산서 한 건의 값 (지급내역형 양식). 정산서에 적힌 공제 줄은 계산에 쓰지 않는다."""

    id: str
    period_start: date
    period_end: date
    gross: Decimal  # 매출액
    reported_payout: Decimal  # 작가지급액 (원천징수 뒤)
    net_revenue: Decimal | None = None  # 회사입금액 (순매출 기준 계약이면 필요)
    reported_settlement: Decimal | None = None  # 정산액 (작가 몫)
    reported_withholding: Decimal | None = None  # 원천징수


@dataclass
class Calculation:
    items: list[PeriodReconciliation]
    unsupported_reason: str | None = None  # 계약 전체 계산 불가 (R10)
    gaps: dict[str, tuple[date, date]] = field(default_factory=dict)


def floor_won(x: Decimal) -> Decimal:
    """원 미만 버림 (0 쪽으로, R3)."""
    return x.quantize(Decimal(1), rounding=ROUND_DOWN)


def floor_ten(x: Decimal) -> Decimal:
    """10원 미만 버림 (R11)."""
    return (x / 10).quantize(Decimal(1), rounding=ROUND_DOWN) * 10


def exact(x: Decimal) -> Decimal:
    """원 미만까지 정확한 값을 보기 좋게: 2400000.00 → 2400000, 411110.8110 → 411110.811."""
    n = x.normalize()
    return n.quantize(Decimal(1)) if n == n.to_integral_value() else n


def won(x: Decimal) -> str:
    """화면에 보이는 금액 표기. 1,234,567 / 452,900.90395"""
    return f"{exact(x):,}"


def withholding(payout: Decimal, on: date) -> tuple[Decimal, Decimal]:
    """R11: (소득세, 지방소득세). 지급액이 0원 이하면 0원."""
    if payout <= 0:
        return ZERO, ZERO
    income = floor_ten(payout * rules.income_tax_rate(on))
    return income, floor_ten(income * rules.LOCAL_TAX_RATE)


def missing_periods(statements: Sequence[StatementInput]) -> dict[str, tuple[date, date]]:
    """앞 정산서와 이어지지 않는 정산서 id → 빠진 기간 (시작일, 종료일)."""
    ordered = _ordered(statements)
    out: dict[str, tuple[date, date]] = {}
    for a, b in pairwise(ordered):
        start = a.period_end + timedelta(days=1)
        if b.period_start > start:
            out[b.id] = (start, b.period_start - timedelta(days=1))
    return out


def _ordered(statements: Sequence[StatementInput]) -> list[StatementInput]:
    return sorted(statements, key=lambda s: (s.period_start, s.period_end, s.id))


def _month(d: date) -> str:
    return f"{d:%Y-%m}"


def calculate(terms: Sequence[Term], statements: Sequence[StatementInput]) -> Calculation:
    """정산서마다 계약서 기준 금액을 계산한다. 결과는 기간 순서."""
    by_key = {t.key: t for t in terms}
    ordered = _ordered(statements)
    gaps = missing_periods(ordered)

    reason = _contract_reason(by_key, ordered, gaps)
    if reason is not None:
        return Calculation([_unsupported(st, reason) for st in ordered], reason, gaps)

    recoup = by_key[TermKey.MG_RECOUP].value
    balance: Decimal = by_key[TermKey.MG_AMOUNT].value  # B_0 = MG 금액 (R9)
    items: list[PeriodReconciliation] = []
    for n, st in enumerate(ordered):
        item, balance, negative = _period(st, by_key, balance, first=n == 0)
        if negative and recoup is MgRecoup.SEPARATE:  # R10: 별도 계약은 음수 몫을 넘길 곳이 없다
            reason = rules.unsupported(_month(st.period_start), rules.NEGATIVE_SEPARATE)
            return Calculation([_unsupported(s, reason) for s in ordered], reason, gaps)
        items.append(item)
    return Calculation(items, None, gaps)


def _contract_reason(
    by_key: dict[TermKey, Term],
    ordered: Sequence[StatementInput],
    gaps: dict[str, tuple[date, date]],
) -> str | None:
    """R10: 계약 전체를 계산하지 않는 이유. 없으면 None."""
    for key in REQUIRED_TERM_KEYS:
        t = by_key.get(key)
        if t is None or t.value is None:
            return rules.unsupported(rules.LABELS[key.value], rules.EMPTY)
        if not t.confirmed:
            raise ValueError(f"확정되지 않은 필수 조건이 있습니다: {key.value}")

    if by_key[TermKey.MG_RECOUP].value is MgRecoup.UNKNOWN:
        return rules.unsupported(rules.LABELS["mg_recoup"], rules.UNKNOWN)
    if isinstance(by_key[TermKey.RS_RATE].value, list):
        return rules.unsupported(rules.LABELS["rs_rate"], rules.TIERED)
    if by_key[TermKey.REVENUE_BASE].value is RevenueBase.OTHER:
        return rules.unsupported(rules.LABELS["revenue_base"], rules.UNKNOWN)

    for a, b in pairwise(ordered):
        if b.period_start <= a.period_end:
            return rules.unsupported(_month(b.period_start), rules.OVERLAP)
    if by_key[TermKey.MG_RECOUP].value is MgRecoup.FROM_RS:
        for st in ordered:
            if st.id in gaps:  # R9: 빠진 달의 회수액을 0원으로 가정하지 않는다
                return rules.unsupported(_month(gaps[st.id][0]), rules.NO_STATEMENT)
    if by_key[TermKey.REVENUE_BASE].value is RevenueBase.NET:
        for st in ordered:
            if st.net_revenue is None:
                return rules.unsupported(_month(st.period_start), rules.NO_NET_REVENUE)
    return None


def _unsupported(st: StatementInput, reason: str) -> PeriodReconciliation:
    return PeriodReconciliation(
        statement_id=st.id,
        period_start=st.period_start,
        period_end=st.period_end,
        status="unsupported",
        reported_payout=st.reported_payout,
        unsupported_reason=reason,
    )


def _period(
    st: StatementInput,
    by_key: dict[TermKey, Term],
    balance: Decimal,
    first: bool,
) -> tuple[PeriodReconciliation, Decimal, bool]:
    """(결과, 다음 기간의 남은 MG, 작가 몫이 음수인가)."""
    ded_term = by_key[TermKey.DEDUCTIONS]
    rs_term = by_key[TermKey.RS_RATE]
    mg_term = by_key[TermKey.MG_AMOUNT]
    recoup_term = by_key[TermKey.MG_RECOUP]
    net_base = by_key[TermKey.REVENUE_BASE].value is RevenueBase.NET
    steps: list[CalcStep] = []

    if net_base:  # R2
        assert st.net_revenue is not None
        g = st.net_revenue
        steps.append(
            CalcStep(
                key="revenue",
                label="매출 G (순매출 기준)",
                value=g,
                formula="정산서 회사입금액. 순매출 기준 계약이라 공제 목록은 쓰지 않습니다 (이중 차감 방지).",
                term_key=TermKey.REVENUE_BASE,
                source_clause_id=by_key[TermKey.REVENUE_BASE].source_clause_id,
            )
        )
        base = g
    else:
        g = st.gross
        steps.append(
            CalcStep(
                key="revenue",
                label="매출 G (총매출 기준)",
                value=g,
                formula="정산서 매출액",
                term_key=TermKey.REVENUE_BASE,
                source_clause_id=by_key[TermKey.REVENUE_BASE].source_clause_id,
            )
        )
        total = ZERO
        deductions: list[Deduction] = ded_term.value
        for d in deductions:  # R1
            if d.rate is not None:
                amount = g * d.rate
                formula = f"{won(g)} × {d.rate} = {won(amount)}"
            else:
                amount = d.amount or ZERO
                formula = "계약서에 적힌 정액"
            total += amount
            steps.append(
                CalcStep(
                    key="deduction",
                    label=f"공제: {d.name}",
                    value=exact(amount),
                    formula=formula,
                    term_key=TermKey.DEDUCTIONS,
                    source_clause_id=ded_term.source_clause_id,
                )
            )
        base = g - total
        steps.append(
            CalcStep(
                key="base",
                label="공제 후 매출 (G − 공제)",
                value=exact(base),
                formula=f"{won(g)} − {won(total)} = {won(base)}",
            )
        )

    rate: Decimal = rs_term.value
    share = base * rate  # 원 미만까지 그대로 (R3)
    steps.append(
        CalcStep(
            key="rs_share",
            label="작가 몫 S (정산액)",
            value=exact(share),
            formula=f"{won(base)} × {rate} = {won(share)}",
            term_key=TermKey.RS_RATE,
            source_clause_id=rs_term.source_clause_id,
        )
    )

    after: Decimal | None
    if recoup_term.value is MgRecoup.FROM_RS:
        steps.append(
            CalcStep(
                key="mg_before",
                label="이 기간 전 남은 MG",
                value=exact(balance),
                formula=(
                    "MG 금액 (첫 정산서부터 회수가 시작된 것으로 계산)"
                    if first
                    else "앞 기간 계산에서 이어받음"
                ),
                term_key=TermKey.MG_AMOUNT,
                source_clause_id=mg_term.source_clause_id,
            )
        )
        payout_exact = max(ZERO, share - balance)
        after = max(ZERO, balance - share)  # 작가 몫이 음수면 남은 MG가 늘어난다 (R5)
        payout = floor_won(payout_exact)
        steps.append(
            CalcStep(
                key="payout",
                label="지급액 P (세전)",
                value=payout,
                formula=f"max(0, {won(share)} − {won(balance)}) = {won(payout_exact)}"
                + (" → 원 미만 버림" if payout != payout_exact else ""),
            )
        )
        steps.append(
            CalcStep(
                key="mg_after",
                label="이 기간 뒤 남은 MG",
                value=exact(after),
                formula=f"max(0, {won(balance)} − {won(share)}) = {won(after)}",
            )
        )
        next_balance = after
    else:  # 별도 (R4)
        payout = floor_won(max(ZERO, share))
        after = None
        steps.append(
            CalcStep(
                key="payout",
                label="지급액 P (세전)",
                value=payout,
                formula="MG를 RS에서 회수하지 않는 계약이라 작가 몫을 그대로 지급액으로 봅니다"
                + (" (원 미만 버림)" if payout != share else ""),
                term_key=TermKey.MG_RECOUP,
                source_clause_id=recoup_term.source_clause_id,
            )
        )
        next_balance = balance

    income, local = withholding(payout, st.period_end)  # R11
    tax = income + local
    rate_pct = f"{rules.income_tax_rate(st.period_end) * 100:g}%"
    steps.append(
        CalcStep(
            key="income_tax",
            label="소득세",
            value=income,
            formula=f"{won(payout)} × {rate_pct} → 10원 미만 버림 = {won(income)}",
        )
    )
    steps.append(
        CalcStep(
            key="local_tax",
            label="지방소득세",
            value=local,
            formula=f"{won(income)} × 10% → 10원 미만 버림 = {won(local)}",
        )
    )
    net = payout - tax
    steps.append(
        CalcStep(
            key="net_payout",
            label="실지급액 (작가지급액)",
            value=net,
            formula=f"{won(payout)} − {won(tax)} = {won(net)}",
        )
    )

    settle = floor_won(share)
    settle_diff = None
    if st.reported_settlement is not None:  # R12
        settle_diff = st.reported_settlement - settle
        steps.append(
            CalcStep(
                key="diff_settlement",
                label="정산액 차이 (정산서 − 계산)",
                value=settle_diff,
                formula=f"{won(st.reported_settlement)} − {won(settle)} = {won(settle_diff)}",
            )
        )
    tax_diff = None
    if st.reported_withholding is not None:  # R11
        tax_diff = st.reported_withholding - tax
        steps.append(
            CalcStep(
                key="diff_withholding",
                label="원천징수 차이 (정산서 − 계산)",
                value=tax_diff,
                formula=f"{won(st.reported_withholding)} − {won(tax)} = {won(tax_diff)}",
            )
        )
    diff = st.reported_payout - net  # R7
    steps.append(
        CalcStep(
            key="diff",
            label="작가지급액 차이 (정산서 − 계산)",
            value=diff,
            formula=f"{won(st.reported_payout)} − {won(net)} = {won(diff)}",
        )
    )

    item = PeriodReconciliation(
        statement_id=st.id,
        period_start=st.period_start,
        period_end=st.period_end,
        status="computed",
        computed_settlement=settle,
        reported_settlement=st.reported_settlement,
        settlement_diff=settle_diff,
        payout_before_tax=payout,
        computed_withholding=tax,
        reported_withholding=st.reported_withholding,
        withholding_diff=tax_diff,
        computed_payout=net,
        reported_payout=st.reported_payout,
        diff=diff,
        mg_balance_after=floor_won(after) if after is not None else None,
        breakdown=steps,
    )
    return item, next_balance, share < 0
