"""M5 엔진 성질과 M6 문장·질문. 계산 규칙 자체는 test_calc_cases.py(손계산 C01–C20)가 확인한다."""

import calendar
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from openbook.engine import StatementInput, calculate, withholding
from openbook.reconcile import StatementLine, StatementWithLines, reconcile
from openbook.reconcile.explain import (
    Q_BREAKDOWN,
    Q_GENERIC_DEDUCTION,
    Q_MG_BALANCE,
    Q_SETTLEMENT,
    Q_WITHHOLDING,
)
from openbook.schemas import Term, TermKey, TermStatus

NOW = datetime(2026, 11, 1, tzinfo=UTC)
APP_FEE = [{"name": "앱마켓 수수료", "rate": "0.3"}]


def terms(mg="1000000", recoup="from_rs", rs="0.6", base="gross", deductions=None, confirm=True):
    values = {
        TermKey.MG_AMOUNT: mg,
        TermKey.MG_RECOUP: recoup,
        TermKey.RS_RATE: rs,
        TermKey.REVENUE_BASE: base,
        TermKey.DEDUCTIONS: APP_FEE if deductions is None else deductions,
    }
    out = []
    for key in TermKey:
        if key in values:
            out.append(
                Term(
                    key=key,
                    value=values[key],
                    status=TermStatus.USER_INPUT,
                    confirmed=confirm,
                    confirmed_at=NOW if confirm else None,
                )
            )
        else:
            out.append(Term(key=key, status=TermStatus.NOT_FOUND))
    return out


def st(sid, month, gross, payout, settle=None, tax=None):
    return StatementInput(
        id=sid,
        period_start=date(2026, month, 1),
        period_end=date(2026, month, calendar.monthrange(2026, month)[1]),
        gross=Decimal(gross),
        reported_payout=Decimal(payout),
        reported_settlement=None if settle is None else Decimal(settle),
        reported_withholding=None if tax is None else Decimal(tax),
    )


def test_withholding_rule():
    # R11: 소득세 3%·지방소득세 10%, 각각 10원 미만 버림
    assert withholding(Decimal(940000), date(2026, 2, 28)) == (28200, 2820)
    assert withholding(Decimal(313413), date(2026, 2, 28)) == (9400, 940)
    assert withholding(Decimal(0), date(2026, 2, 28)) == (0, 0)


def test_breakdown_order():
    (r,) = calculate(terms(), [st("a", 1, "1000000", "0")]).items
    assert [s.key for s in r.breakdown] == [
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
        "diff",
    ]


def test_optional_statement_columns_are_compared_only_when_given():
    # 1,000,000 − 300,000 = 700,000 × 0.6 = 420,000 → MG 0이면 지급 420,000, 원천징수 13,860
    (r,) = calculate(terms(mg="0"), [st("a", 1, "1000000", "406140")]).items
    assert (r.settlement_diff, r.withholding_diff, r.diff) == (None, None, 0)
    (r,) = calculate(
        terms(mg="0"), [st("a", 1, "1000000", "406140", settle="420000", tax="13860")]
    ).items
    assert (r.settlement_diff, r.withholding_diff, r.diff) == (0, 0, 0)


def test_rejects_unconfirmed_terms():
    with pytest.raises(ValueError):
        calculate(terms(confirm=False), [st("a", 1, "100", "0")])


def test_engine_does_not_import_llm_or_network():
    src = Path(__file__).resolve().parents[1] / "src" / "openbook" / "engine"
    text = "".join(p.read_text(encoding="utf-8") for p in src.glob("*.py"))
    for banned in ("openbook.terms", "httpx", "openai", "float(", "round("):
        assert banned not in text


def test_reconcile_sentences_and_questions():
    # 1월: 몫 420,000 → MG 1,000,000 중 580,000 남음, 지급 0
    # 2월: 1,500,000 − 450,000 = 1,050,000 × 0.6 = 630,000 → 지급 50,000, 원천징수 1,650 → 48,350
    lines = (
        StatementLine("앱마켓 수수료", Decimal(450000)),  # 계약서 기준과 같음 → 질문 없음
        StatementLine("플랫폼 운영비", Decimal(10000)),  # 계약서에 없음
    )
    report = reconcile(
        "k1",
        terms(),
        [
            StatementWithLines(st("m1", 1, "1000000", "0", settle="420000", tax="0")),
            StatementWithLines(st("m2", 2, "1500000", "40000", settle="600000", tax="1650"), lines),
        ],
    )
    m1, m2 = report.items
    assert m2.summary == (
        "계약서 기준으로 계산한 작가지급액(원천징수 뒤)은 48,350원, 정산서에는 40,000원, "
        "차이는 -8,350원입니다. 정산액(작가 몫)은 계약서 기준 630,000원, 정산서 600,000원으로 "
        "차이는 -30,000원입니다."
    )
    assert m1.questions == [Q_MG_BALANCE]  # 차이 0
    assert m2.questions[:2] == [Q_SETTLEMENT, Q_BREAKDOWN]
    assert Q_WITHHOLDING not in m2.questions  # 원천징수는 맞음
    assert any("플랫폼 운영비" in q for q in m2.questions)
    assert not any("'앱마켓 수수료'" in q for q in m2.questions)
    assert report.unsupported_reason is None

    odd = reconcile(
        "k1",
        terms(),
        [
            StatementWithLines(
                st("m1", 1, "1000000", "0"),
                (
                    StatementLine("앱 마켓수수료", Decimal(1)),
                    StatementLine("부당 공제", Decimal(5)),
                ),
            )
        ],
    )
    qs = odd.items[0].questions
    assert any("300,000원" in q for q in qs)  # 금액이 다르면 묻는다
    assert Q_GENERIC_DEDUCTION in qs and not any("부당" in q for q in qs)  # 금지 표현 필터


def test_unsupported_contract_hides_amounts_and_asks_for_missing_month():
    report = reconcile(
        "k1",
        terms(),
        [
            StatementWithLines(st("m1", 1, "1000000", "0")),
            StatementWithLines(st("m3", 3, "1", "0")),
        ],
    )
    assert report.unsupported_reason == "계산 불가: 2026-02이(가) 정산서 없음"
    assert all(i.status == "unsupported" and i.computed_payout is None for i in report.items)
    assert (
        report.items[1].summary == "계산 불가: 2026-02이(가) 정산서 없음. 금액은 표시하지 않습니다."
    )
    assert (
        "2026-02-01 ~ 2026-02-28 기간의 정산서를 보내 주실 수 있을까요?"
        in report.items[1].questions
    )

    # 별도 계약은 빠진 달이 계산에 영향이 없어 계산하고, 빠진 기간만 묻는다
    sep = reconcile(
        "k1",
        terms(recoup="separate"),
        [
            StatementWithLines(st("m1", 1, "1000000", "0")),
            StatementWithLines(st("m3", 3, "1", "0")),
        ],
    )
    assert sep.unsupported_reason is None
    assert any("2026-02-01" in q for q in sep.items[1].questions)


def test_summary_mentions_withholding_difference():
    # 444,135 × 3% = 13,324.05 → 13,320, 지방세 1,330 → 14,650. 정산서는 8.8%로 39,080을 뗌
    report = reconcile(
        "k1",
        terms(mg="0", recoup="separate", rs="1", deductions=[]),
        [StatementWithLines(st("m1", 2, "444135", "405055", settle="444135", tax="39080"))],
    )
    (r,) = report.items
    assert r.summary.endswith(
        "원천징수는 계약서 기준(3.3%) 14,650원, 정산서 39,080원으로 차이는 24,430원입니다."
    )
    assert r.questions[0] == Q_WITHHOLDING
