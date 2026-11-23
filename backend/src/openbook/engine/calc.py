"""M5 계산 엔진. 순수 함수, Decimal만 쓴다.

LLM·파일·네트워크·시간·난수를 쓰지 않는다. 규칙은 engine/rules.py(임시 안)를 따른다.
입력은 사용자가 확정한 조건과 정산서 값뿐이다. 필수 조건이 확정되지 않았으면 ValueError.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
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
    """계산에 쓰는 정산서 값 (정산서에 적힌 공제는 계산에 쓰지 않는다: R2)."""

    id: str
    period_start: date
    period_end: date
    gross: Decimal
    reported_payout: Decimal


def floor_won(x: Decimal) -> Decimal:
    """원 미만 버림 (R3)."""
    return x.quantize(Decimal(1), rounding=ROUND_DOWN)


def won(x: Decimal) -> str:
    """화면에 보이는 금액 표기. 1,234,567"""
    return f"{x:,}"


def calculate(
    terms: Sequence[Term], statements: Sequence[StatementInput]
) -> list[PeriodReconciliation]:
    """정산서마다 계약서 기준 지급액을 계산한다. 결과는 기간 순서."""
    by_key = {t.key: t for t in terms}
    for key in REQUIRED_TERM_KEYS:
        t = by_key.get(key)
        if t is None or not t.confirmed or t.value is None:
            raise ValueError(f"확정되지 않은 필수 조건이 있습니다: {key.value}")

    ordered = sorted(statements, key=lambda s: (s.period_start, s.period_end, s.id))
    overlapping = _overlapping_ids(ordered)
    gaps = missing_periods(ordered)
    reason = _unsupported_reason(by_key)
    recoup = by_key[TermKey.MG_RECOUP].value

    results: list[PeriodReconciliation] = []
    balance: Decimal | None = by_key[TermKey.MG_AMOUNT].value  # B_0 = MG 금액 (R9)
    first = True
    for st in ordered:
        why = reason or (rules.UNSUPPORTED_OVERLAP if st.id in overlapping else None)
        if why is None and recoup is MgRecoup.FROM_RS and balance is None:
            why = rules.UNSUPPORTED_CHAIN
        if why is None and recoup is MgRecoup.FROM_RS and st.id in gaps and balance:
            why = rules.UNSUPPORTED_GAP  # R11: 빠진 기간에 회수된 MG를 모른다
        if why is not None:
            results.append(_unsupported(st, why))
            balance = None if recoup is MgRecoup.FROM_RS else balance
            continue
        result, balance = _period(st, by_key, balance, first)
        results.append(result)
        first = False
    return results


def _unsupported_reason(by_key: dict[TermKey, Term]) -> str | None:
    if isinstance(by_key[TermKey.RS_RATE].value, list):
        return rules.UNSUPPORTED_TIERED_RS
    if by_key[TermKey.REVENUE_BASE].value is RevenueBase.OTHER:
        return rules.UNSUPPORTED_REVENUE_OTHER
    if by_key[TermKey.MG_RECOUP].value is MgRecoup.UNKNOWN:
        return rules.UNSUPPORTED_RECOUP_UNKNOWN
    return None


def _overlapping_ids(ordered: Sequence[StatementInput]) -> set[str]:
    out: set[str] = set()
    for a, b in pairwise(ordered):
        if b.period_start <= a.period_end:
            out.update((a.id, b.id))
    return out


def missing_periods(statements: Sequence[StatementInput]) -> dict[str, tuple[date, date]]:
    """R11: 앞 정산서와 이어지지 않는 정산서 id → 빠진 기간 (시작일, 종료일)."""
    ordered = sorted(statements, key=lambda s: (s.period_start, s.period_end, s.id))
    out: dict[str, tuple[date, date]] = {}
    for a, b in pairwise(ordered):
        start = a.period_end + timedelta(days=1)
        if b.period_start > start:
            out[b.id] = (start, b.period_start - timedelta(days=1))
    return out


def floor_ten(x: Decimal) -> Decimal:
    """10원 미만 버림."""
    return (x / 10).quantize(Decimal(1), rounding=ROUND_DOWN) * 10


def after_withholding(payout: Decimal) -> Decimal:
    """R12 (표시만): 지급액에서 원천징수 3.3%를 뗀 금액. 소득세 3%, 지방소득세는 소득세의 10%."""
    income_tax = floor_ten(payout * Decimal("0.03"))
    local_tax = floor_ten(income_tax * Decimal("0.1"))
    return payout - income_tax - local_tax


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
    balance: Decimal | None,
    first: bool,
) -> tuple[PeriodReconciliation, Decimal | None]:
    ded_term = by_key[TermKey.DEDUCTIONS]
    rs_term = by_key[TermKey.RS_RATE]
    mg_term = by_key[TermKey.MG_AMOUNT]
    recoup = by_key[TermKey.MG_RECOUP].value
    g = st.gross
    steps: list[CalcStep] = []

    total = ZERO
    deductions: list[Deduction] = ded_term.value
    for d in deductions:
        if d.rate is not None:
            amount = floor_won(g * d.rate)  # R1, R3
            formula = f"{won(g)} × {d.rate} = {won(amount)} (원 미만 버림)"
        else:
            amount = d.amount
            formula = "계약서에 적힌 정액"
        total += amount
        steps.append(
            CalcStep(
                key="deduction",
                label=f"공제: {d.name}",
                value=amount,
                formula=formula,
                term_key=TermKey.DEDUCTIONS,
                source_clause_id=ded_term.source_clause_id,
            )
        )

    base = g - total
    if base < 0:  # R5
        return _unsupported(st, rules.UNSUPPORTED_NEGATIVE_BASE), None
    steps.append(
        CalcStep(
            key="base",
            label="RS 기준 금액 (총매출 − 공제)",
            value=base,
            formula=f"{won(g)} − {won(total)} = {won(base)}",
        )
    )

    rate: Decimal = rs_term.value
    share = floor_won(base * rate)  # R3
    steps.append(
        CalcStep(
            key="rs_share",
            label="작가 몫 (RS)",
            value=share,
            formula=f"{won(base)} × {rate} = {won(share)} (원 미만 버림)",
            term_key=TermKey.RS_RATE,
            source_clause_id=rs_term.source_clause_id,
        )
    )

    if recoup is MgRecoup.FROM_RS:
        assert balance is not None
        steps.append(
            CalcStep(
                key="mg_before",
                label="이 기간 전 남은 MG",
                value=balance,
                formula=(
                    "MG 금액 (첫 정산서부터 회수가 시작된 것으로 계산)"
                    if first
                    else "앞 기간 계산에서 이어받음"
                ),
                term_key=TermKey.MG_AMOUNT,
                source_clause_id=mg_term.source_clause_id,
            )
        )
        payout = max(ZERO, share - balance)
        after: Decimal | None = max(ZERO, balance - share)
        steps.append(
            CalcStep(
                key="payout",
                label="계약서 기준 지급액",
                value=payout,
                formula=f"max(0, {won(share)} − {won(balance)}) = {won(payout)}",
            )
        )
        steps.append(
            CalcStep(
                key="mg_after",
                label="이 기간 뒤 남은 MG",
                value=after,
                formula=f"max(0, {won(balance)} − {won(share)}) = {won(after)}",
            )
        )
    else:  # separate (R4)
        payout, after = share, None
        steps.append(
            CalcStep(
                key="payout",
                label="계약서 기준 지급액",
                value=payout,
                formula="MG를 RS에서 회수하지 않는 계약이라 작가 몫을 그대로 지급액으로 봅니다.",
                term_key=TermKey.MG_RECOUP,
                source_clause_id=by_key[TermKey.MG_RECOUP].source_clause_id,
            )
        )

    diff = payout - st.reported_payout  # R7
    steps.append(
        CalcStep(
            key="diff",
            label="차이 (계약서 기준 − 정산서)",
            value=diff,
            formula=f"{won(payout)} − {won(st.reported_payout)} = {won(diff)}",
        )
    )
    result = PeriodReconciliation(
        statement_id=st.id,
        period_start=st.period_start,
        period_end=st.period_end,
        status="computed",
        computed_payout=payout,
        reported_payout=st.reported_payout,
        diff=diff,
        mg_balance_after=after,
        breakdown=steps,
    )
    return result, (after if recoup is MgRecoup.FROM_RS else balance)
