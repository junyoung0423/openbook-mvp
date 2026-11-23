"""M6 대조·설명. 숫자는 엔진 출력을 치환 변수로만 쓰고, 문장은 금지 표현 필터를 통과한다."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from openbook.engine import RULES_VERSION, StatementInput, calculate, missing_periods
from openbook.reconcile.explain import StatementLine, questions, summary
from openbook.schemas.reconciliation import ReconciliationReport
from openbook.schemas.terms import Term, TermKey


@dataclass(frozen=True)
class StatementWithLines:
    statement: StatementInput
    lines: tuple[StatementLine, ...] = field(default_factory=tuple)


def reconcile(
    contract_id: str, terms: Sequence[Term], statements: Sequence[StatementWithLines]
) -> ReconciliationReport:
    """계산(M5) 후 결과 문장과 확인 질문을 붙인다. 필수 조건이 미확정이면 ValueError."""
    inputs = [s.statement for s in statements]
    results = calculate(terms, inputs)
    gaps = missing_periods(inputs)
    by_key = {t.key: t for t in terms}
    lines = {s.statement.id: s.lines for s in statements}
    recoup = by_key[TermKey.MG_RECOUP].value
    deductions = by_key[TermKey.DEDUCTIONS].value
    for r in results:
        r.summary = summary(r)
        r.questions = questions(
            r, lines[r.statement_id], deductions, recoup, gaps.get(r.statement_id)
        )
    return ReconciliationReport(contract_id=contract_id, items=results, rules_version=RULES_VERSION)


__all__ = ["StatementLine", "StatementWithLines", "reconcile"]
