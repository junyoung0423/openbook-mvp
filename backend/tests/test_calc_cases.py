"""계산 규칙 R1–R12 손계산 정답 케이스 C01–C20 (허정민 님 검산표, 금액은 모두 가상).

케이스 파일: tests/calc_cases/*.json · 설명: docs/calc-rules/손계산_케이스_검산표.md
정답은 엔진 코드와 무관하게 규칙 문장만 보고 계산한 값이다. 엔진이 하나라도 다르면 실패한다.
"""

from __future__ import annotations

import calendar
import json
from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from openbook.engine import StatementInput, calculate
from openbook.schemas import Term, TermKey, TermStatus

CASES = sorted((Path(__file__).parent / "calc_cases").glob("C*.json"))
NOW = datetime(2026, 11, 23, tzinfo=UTC)
RECOUP = {"post": "from_rs", "separate": "separate", "unknown": "unknown"}


def _term(key: TermKey, value) -> Term:
    if value is None:
        return Term(key=key, status=TermStatus.NOT_FOUND)
    return Term(
        key=key, value=value, status=TermStatus.USER_INPUT, confirmed=True, confirmed_at=NOW
    )


def _rs(value):
    if isinstance(
        value, list
    ):  # 구간별: [{"upto": "10000000", "rate": "0.5"}, {"upto": null, ...}]
        tiers, start = [], "0"
        for t in value:
            tiers.append({"from_amount": start, "to_amount": t["upto"], "rate": t["rate"]})
            start = t["upto"] or start
        return tiers
    return value


def terms_of(contract: dict) -> list[Term]:
    deductions = [
        {"name": d["name"], "rate": d["value"]}
        if d["type"] == "ratio"
        else {"name": d["name"], "amount": d["value"]}
        for d in contract["deductions"]
    ]
    values = {
        TermKey.MG_AMOUNT: str(contract["mg_amount"]),
        TermKey.MG_RECOUP: RECOUP[contract["mg_recoup"]],
        TermKey.RS_RATE: _rs(contract["rs_rate"]),
        TermKey.REVENUE_BASE: contract["revenue_base"],
        TermKey.DEDUCTIONS: deductions,
    }
    return [_term(k, v) for k, v in values.items()]


def statements_of(case: dict) -> list[StatementInput]:
    out = []
    for m in case["statement"]:
        y, mo = map(int, m["month"].split("-"))
        total: dict[str, Decimal] = defaultdict(Decimal)
        for row in m["rows"]:  # 한 달에 여러 줄이면 더한다
            for col in ("매출액", "회사입금액", "정산액", "원천징수", "작가지급액"):
                total[col] += Decimal(row[col])
        out.append(
            StatementInput(
                id=m["month"],
                period_start=date(y, mo, 1),
                period_end=date(y, mo, calendar.monthrange(y, mo)[1]),
                gross=total["매출액"],
                net_revenue=total["회사입금액"],
                reported_settlement=total["정산액"],
                reported_withholding=total["원천징수"],
                reported_payout=total["작가지급액"],
            )
        )
    return out


def _step(item, key):
    return [s.value for s in item.breakdown if s.key == key]


@pytest.mark.parametrize("path", CASES, ids=[p.stem for p in CASES])
def test_hand_calculated_case(path: Path):
    case = json.loads(path.read_text(encoding="utf-8"))
    result = calculate(terms_of(case["contract"]), statements_of(case))
    expected = case["expected"]

    if not expected["computable"]:
        assert result.unsupported_reason == expected["reason"]
        for item in result.items:  # 금액은 하나도 표시하지 않는다 (R10)
            assert item.status == "unsupported"
            assert item.computed_payout is None and item.computed_settlement is None
            assert item.breakdown == []
        return

    assert result.unsupported_reason is None
    separate = case["contract"]["mg_recoup"] == "separate"
    assert len(result.items) == len(expected["months"])
    for item, want in zip(result.items, expected["months"], strict=True):
        where = f"{path.stem} {want['month']}"
        assert item.status == "computed", where
        assert _step(item, "revenue") == [Decimal(want["G"])], where
        if want["D"] is None:  # 순매출 기준: 공제 목록을 쓰지 않는다 (R2)
            assert _step(item, "deduction") == [], where
        else:
            assert sum(_step(item, "deduction")) == Decimal(want["D"]), where
        assert _step(item, "rs_share") == [Decimal(want["S"])], where
        assert item.computed_settlement == want["S_display"], where
        assert item.payout_before_tax == want["P"], where
        assert item.computed_withholding == want["withholding"], where
        assert item.computed_payout == want["net_payout"], where
        if separate:
            assert item.mg_balance_after is None, where
        else:
            assert _step(item, "mg_after") == [Decimal(want["B"])], where
            assert item.mg_balance_after == want["B_display"], where
        assert item.settlement_diff == want["diff_settle_R12"], where
        assert item.withholding_diff == want["diff_withholding_R11"], where
        assert item.diff == want["diff_net_payout_R7"], where


def test_all_twenty_cases_present():
    assert [p.stem for p in CASES] == [f"C{n:02d}" for n in range(1, 21)]
