"""M5 계산 엔진과 M6 문장. 정답은 모두 손으로 계산한 값이다 (가상 값)."""

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from openbook.engine import StatementInput, calculate, rules
from openbook.reconcile import StatementLine, StatementWithLines, reconcile
from openbook.reconcile.explain import Q_GENERIC_DEDUCTION, Q_MG_BALANCE
from openbook.schemas import Term, TermKey, TermStatus

NOW = datetime(2026, 11, 1, tzinfo=UTC)
APP_FEE = [{"name": "앱마켓 수수료", "rate": "0.3"}]


def terms(mg="1000000", recoup="from_rs", rs="0.6", base="net", deductions=None, confirm=True):
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


def st(sid, month, gross, reported, day_end=28):
    return StatementInput(
        id=sid,
        period_start=date(2026, month, 1),
        period_end=date(2026, month, day_end),
        gross=Decimal(gross),
        reported_payout=Decimal(reported),
    )


def test_mg_recoup_across_months():
    # 1월: 1,000,000 − 300,000 = 700,000 × 0.6 = 420,000 → 지급 0, 남은 MG 580,000
    # 2월: 1,500,000 − 450,000 = 1,050,000 × 0.6 = 630,000 → 지급 50,000, 남은 MG 0
    # 3월: 500,000 − 150,000 = 350,000 × 0.6 = 210,000 → 지급 210,000
    out = calculate(
        terms(),
        [
            st("m3", 3, "500000", "250000"),
            st("m1", 1, "1000000", "0"),
            st("m2", 2, "1500000", "40000"),
        ],
    )
    assert [r.statement_id for r in out] == ["m1", "m2", "m3"]  # 기간 순으로 이어 계산
    assert [r.computed_payout for r in out] == [0, 50000, 210000]
    assert [r.mg_balance_after for r in out] == [580000, 0, 0]
    assert [r.diff for r in out] == [0, 10000, -40000]  # 계약서 기준 − 정산서
    keys = [s.key for s in out[0].breakdown]
    assert keys == ["deduction", "base", "rs_share", "mg_before", "payout", "mg_after", "diff"]


def test_share_equal_to_balance_and_flooring():
    (r,) = calculate(terms(mg="420000"), [st("a", 1, "1000000", "0")])
    assert (r.computed_payout, r.mg_balance_after) == (0, 0)
    # 1,000,001 × 0.3 = 300,000.3 → 300,000 / 700,001 × 0.6 = 420,000.6 → 420,000
    (r,) = calculate(terms(mg="0"), [st("a", 1, "1000001", "420000")])
    assert r.breakdown[0].value == 300000 and r.computed_payout == 420000 and r.diff == 0


def test_separate_recoup_and_fixed_deduction():
    # 1,000,000 − 100,000 = 900,000 × 0.5 = 450,000, MG 회수 없음
    t = terms(recoup="separate", rs="0.5", deductions=[{"name": "제작 지원금", "amount": "100000"}])
    (r,) = calculate(t, [st("a", 1, "1000000", "450000")])
    assert r.computed_payout == 450000 and r.diff == 0 and r.mg_balance_after is None


def test_zero_revenue_keeps_balance():
    out = calculate(terms(), [st("a", 1, "0", "0"), st("b", 2, "1000000", "0")])
    assert out[0].computed_payout == 0 and out[0].mg_balance_after == 1000000
    assert out[1].mg_balance_after == 580000


def test_unsupported_cases():
    tiered = terms(rs=[{"from_amount": "0", "rate": "0.5"}])
    assert calculate(tiered, [st("a", 1, "100", "0")])[0].unsupported_reason == (
        rules.UNSUPPORTED_TIERED_RS
    )
    for kw, reason in [
        ({"base": "other"}, rules.UNSUPPORTED_REVENUE_OTHER),
        ({"recoup": "unknown"}, rules.UNSUPPORTED_RECOUP_UNKNOWN),
    ]:
        assert calculate(terms(**kw), [st("a", 1, "100", "0")])[0].unsupported_reason == reason

    big = terms(deductions=[{"name": "비용", "amount": "2000000"}])
    out = calculate(big, [st("a", 1, "1000000", "0"), st("b", 2, "3000000", "0")])
    assert out[0].unsupported_reason == rules.UNSUPPORTED_NEGATIVE_BASE
    assert out[1].unsupported_reason == rules.UNSUPPORTED_CHAIN  # 남은 MG를 모름
    assert out[1].computed_payout is None

    overlap = [
        st("a", 1, "100", "0"),
        StatementInput("b", date(2026, 1, 15), date(2026, 2, 14), Decimal(1), Decimal(0)),
    ]
    assert {r.unsupported_reason for r in calculate(terms(), overlap)} == {
        rules.UNSUPPORTED_OVERLAP
    }


def test_rejects_unconfirmed_terms():
    with pytest.raises(ValueError):
        calculate(terms(confirm=False), [st("a", 1, "100", "0")])


def test_engine_does_not_import_llm_or_network():
    src = Path(__file__).resolve().parents[1] / "src" / "openbook" / "engine"
    text = "".join(p.read_text(encoding="utf-8") for p in src.glob("*.py"))
    for banned in ("openbook.terms", "httpx", "openai", "float(", "round("):
        assert banned not in text


def test_reconcile_sentences_and_questions():
    lines = (
        StatementLine("앱마켓 수수료", Decimal(450000)),  # 계약서 기준과 같음 → 질문 없음
        StatementLine("플랫폼 운영비", Decimal(10000)),  # 계약서에 없음
    )
    report = reconcile(
        "k1",
        terms(),
        [
            StatementWithLines(st("m1", 1, "1000000", "0")),
            StatementWithLines(st("m2", 2, "1500000", "40000"), lines),
        ],
    )
    m1, m2 = report.items
    assert (
        m2.summary
        == "계약서 기준으로 계산하면 50,000원, 정산서에는 40,000원, 차이는 10,000원입니다."
    )
    assert m1.questions == [Q_MG_BALANCE]  # 차이 0
    assert any("플랫폼 운영비" in q for q in m2.questions)
    assert not any("'앱마켓 수수료'" in q for q in m2.questions)
    assert report.rules_version.startswith("provisional")

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
