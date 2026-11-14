import copy
import json
from decimal import Decimal
from pathlib import Path

import pytest

from openbook.clauses import split_clauses
from openbook.schemas import TermKey, TermStatus
from openbook.terms import extract_terms

SAMPLE_A = Path(__file__).resolve().parents[2] / "data" / "samples" / "sample_a.txt"
CLAUSES = split_clauses(SAMPLE_A.read_text(encoding="utf-8")).clauses

MG_QUOTE = '갑은 을에게 선급금(이하 "MG") 5,000,000원을 계약 체결일로부터 30일 이내에 지급한다.'
RS_QUOTE = "을의 수익배분율은 순매출의 60%로 한다."


def _item(key, value, clause_id, quote):
    return {"key": key, "value": value, "clause_id": clause_id, "quote": quote}


# 샘플 계약서(sample_a)를 사람이 읽고 정리한 정답 응답. 전부 계약서 원문 그대로의 인용이다.
GOOD = [
    _item("mg_amount", "5000000", "c-04", MG_QUOTE),
    _item("mg_pay_date", "계약 체결일로부터 30일 이내", "c-04", MG_QUOTE),
    _item(
        "mg_recoup",
        "from_rs",
        "c-04",
        "MG는 제5조에 따른 을의 수익배분금에서 우선 차감하여 회수한다.",
    ),
    _item(
        "mg_carryover",
        "forgiven",
        "c-04",
        "계약기간 종료 시 회수되지 않은 MG는 갑이 을에게 반환을 요구하지 않는다.",
    ),
    _item("rs_rate", "0.6", "c-05", RS_QUOTE),
    _item("revenue_base", "net", "c-05", RS_QUOTE),
    _item(
        "deductions", [{"name": "결제 수수료", "rate": "0.1"}], "c-06", "결제 수수료: 총매출의 10%"
    ),
    _item(
        "settlement_cycle",
        "monthly",
        "c-07",
        "갑은 매월 말일에 정산하고, 정산서를 다음 달 10일까지 을에게 제공한다.",
    ),
    _item(
        "payment_day",
        "정산서 제공일로부터 15일 이내",
        "c-07",
        "갑은 정산서 제공일로부터 15일 이내에 정산금을 지급한다.",
    ),
]


class FakeLLM:
    def __init__(self, items=None, raw=None):
        self.raw = raw if raw is not None else json.dumps({"terms": items}, ensure_ascii=False)
        self.calls = []

    def complete(self, system, user):
        self.calls.append((system, user))
        return self.raw


def run(items=None, raw=None):
    return extract_terms("k1", CLAUSES, FakeLLM(items, raw))


def term(result, key):
    return next(t for t in result.terms.terms if t.key == key)


def modified(key, **changes):
    items = copy.deepcopy(GOOD)
    for it in items:
        if it["key"] == key:
            it.update(changes)
    return items


# ---- 정상 경로


def test_good_response_extracts_all_nine():
    res = run(GOOD)
    assert len(res.terms.terms) == 9
    assert all(t.status is TermStatus.EXTRACTED for t in res.terms.terms)
    assert res.warnings == []
    assert term(res, TermKey.MG_AMOUNT).value == Decimal(5_000_000)
    assert term(res, TermKey.RS_RATE).value == Decimal("0.6")
    assert term(res, TermKey.REVENUE_BASE).value.value == "net"
    assert term(res, TermKey.DEDUCTIONS).value[0].rate == Decimal("0.1")
    assert term(res, TermKey.MG_AMOUNT).source_clause_id == "c-04"


def test_nothing_is_confirmed_by_the_extractor():
    res = run(GOOD)
    assert not any(t.confirmed for t in res.terms.terms)
    assert not res.terms.all_confirmed


def test_prompt_contains_clause_ids_and_text():
    llm = FakeLLM(GOOD)
    extract_terms("k1", CLAUSES, llm)
    system, user = llm.calls[0]
    assert "[c-04] 제4조 선급금" in user
    assert "5,000,000원" in user
    assert "null" in system and "quote" in system


def test_wrapped_in_code_fence_and_extra_text():
    raw = "```json\n" + json.dumps({"terms": GOOD}, ensure_ascii=False) + "\n```"
    assert all(t.status is TermStatus.EXTRACTED for t in run(raw=raw).terms.terms)


def test_quote_whitespace_and_quote_marks_tolerated():
    items = modified("rs_rate", quote="“을의   수익배분율은 순매출의 60%로\n한다.”")
    assert term(run(items), TermKey.RS_RATE).status is TermStatus.EXTRACTED


# ---- 값을 버려야 하는 경우 (틀린 값보다 찾지 못함)


def test_invented_quote_is_rejected():
    res = run(modified("rs_rate", quote="을의 수익배분율은 순매출의 70%로 한다."))
    t = term(res, TermKey.RS_RATE)
    assert t.status is TermStatus.NOT_FOUND and t.value is None
    assert any("rs_rate" in w and "원문" in w for w in res.warnings)


def test_amount_not_in_quote_is_rejected():
    res = run(modified("mg_amount", value="6000000"))
    assert term(res, TermKey.MG_AMOUNT).status is TermStatus.NOT_FOUND
    assert any("mg_amount" in w for w in res.warnings)


def test_rate_not_in_quote_is_rejected():
    assert (
        term(run(modified("rs_rate", value="0.7")), TermKey.RS_RATE).status is TermStatus.NOT_FOUND
    )


def test_percent_written_as_whole_number_is_rejected_by_schema():
    assert (
        term(run(modified("rs_rate", value="60")), TermKey.RS_RATE).status is TermStatus.NOT_FOUND
    )


def test_deduction_rate_must_be_in_quote():
    items = modified("deductions", value=[{"name": "결제 수수료", "rate": "0.2"}])
    assert term(run(items), TermKey.DEDUCTIONS).status is TermStatus.NOT_FOUND


def test_invalid_enum_value_is_rejected():
    assert (
        term(run(modified("revenue_base", value="profit")), TermKey.REVENUE_BASE).status
        is TermStatus.NOT_FOUND
    )


def test_missing_quote_is_rejected():
    res = run(modified("mg_recoup", quote=None))
    assert term(res, TermKey.MG_RECOUP).status is TermStatus.NOT_FOUND
    assert any("quote" in w for w in res.warnings)


def test_null_value_is_plain_not_found_without_warning():
    res = run(modified("mg_pay_date", value=None, clause_id=None, quote=None))
    assert term(res, TermKey.MG_PAY_DATE).status is TermStatus.NOT_FOUND
    assert res.warnings == []


def test_missing_keys_become_not_found():
    res = run([GOOD[0]])
    assert len(res.terms.terms) == 9
    assert term(res, TermKey.MG_AMOUNT).status is TermStatus.EXTRACTED
    assert term(res, TermKey.RS_RATE).status is TermStatus.NOT_FOUND


def test_unknown_key_is_ignored_with_warning():
    res = run(GOOD + [_item("profit_margin", "0.3", "c-05", RS_QUOTE)])
    assert len(res.terms.terms) == 9
    assert any("profit_margin" in w for w in res.warnings)


@pytest.mark.parametrize("raw", ["죄송합니다. 찾지 못했습니다.", "{not json", '{"terms": "x"}', ""])
def test_unparseable_answer_makes_everything_not_found(raw):
    res = run(raw=raw)
    assert all(t.status is TermStatus.NOT_FOUND for t in res.terms.terms)
    assert res.warnings


# ---- 근거 조항 번호 바로잡기


def test_wrong_clause_id_is_corrected_when_quote_is_unique():
    res = run(modified("rs_rate", clause_id="c-09"))
    t = term(res, TermKey.RS_RATE)
    assert t.status is TermStatus.EXTRACTED and t.source_clause_id == "c-05"
    assert any("바로잡" in w for w in res.warnings)


def test_unknown_clause_id_with_unique_quote_is_corrected():
    t = term(run(modified("rs_rate", clause_id="c-99")), TermKey.RS_RATE)
    assert t.source_clause_id == "c-05"


# ---- 금액 표기 변형


def test_amount_written_in_man_won_is_supported():
    clauses = split_clauses(
        "제1조 (선급금)\n갑은 을에게 선급금 500만원을 지급한다.\n제2조 (기간)\n1년으로 한다.\n"
    ).clauses
    items = [_item("mg_amount", "5000000", "c-01", "갑은 을에게 선급금 500만원을 지급한다.")]
    res = extract_terms("k2", clauses, FakeLLM(items))
    assert term(res, TermKey.MG_AMOUNT).value == Decimal(5_000_000)


# ---- 실제 Upstage 호출에서 나온 모양 (값 정리)


def test_json_string_wrapped_rs_rate_with_single_open_tier_becomes_plain_rate():
    wrapped = json.dumps([{"from_amount": "0", "to_amount": "", "rate": "0.6"}])
    t = term(run(modified("rs_rate", value=wrapped)), TermKey.RS_RATE)
    assert t.status is TermStatus.EXTRACTED and t.value == Decimal("0.6")


def test_multi_tier_rs_rate_stays_a_tier_list():
    clauses = split_clauses(
        "제1조 (수익배분)\n구간별 배분: 100만원 이하 50%, 100만원 초과 70%로 한다.\n제2조 (기간)\n1년으로 한다.\n"
    ).clauses
    tiers = [
        {"from_amount": "0", "to_amount": "1000000", "rate": "0.5"},
        {"from_amount": "1000000", "to_amount": None, "rate": "0.7"},
    ]
    items = [_item("rs_rate", tiers, "c-01", "100만원 이하 50%, 100만원 초과 70%로 한다.")]
    t = term(extract_terms("k3", clauses, FakeLLM(items)), TermKey.RS_RATE)
    assert t.status is TermStatus.EXTRACTED and len(t.value) == 2


DEDUCTION_QUOTE = "결제 수수료: 총매출의 10%\n2. 마케팅 비용: 을이 사전에 서면으로 동의한 금액"


def test_unquantified_deduction_is_dropped_with_a_warning_for_the_user():
    value = [{"name": "결제 수수료", "rate": "0.1"}, {"name": "마케팅 비용", "amount": None}]
    res = run(modified("deductions", value=value, quote=DEDUCTION_QUOTE))
    t = term(res, TermKey.DEDUCTIONS)
    assert t.status is TermStatus.EXTRACTED
    assert [d.name for d in t.value] == ["결제 수수료"]
    assert any("마케팅 비용" in w and "직접 입력" in w for w in res.warnings)


def test_all_deductions_unquantified_means_not_found():
    value = [{"name": "마케팅 비용", "amount": None}]
    res = run(modified("deductions", value=value, quote=DEDUCTION_QUOTE))
    assert term(res, TermKey.DEDUCTIONS).status is TermStatus.NOT_FOUND
    assert any("마케팅 비용" in w for w in res.warnings)


def test_json_string_wrapped_deductions():
    wrapped = json.dumps([{"name": "결제 수수료", "rate": "0.1"}], ensure_ascii=False)
    t = term(run(modified("deductions", value=wrapped)), TermKey.DEDUCTIONS)
    assert t.status is TermStatus.EXTRACTED and t.value[0].rate == Decimal("0.1")


# ---- 구간표 검증 (실제 호출에서 없는 구간표를 만든 사례)

SAMPLE_B_QUOTE = "인세율은 매출의 70%로 한다.\n5.2 단, 해외 판매분은 매출의 50%로 한다."


def _b_clauses():
    raw = (SAMPLE_A.parent / "sample_b.txt").read_text(encoding="utf-8")
    return split_clauses(raw).clauses


def test_invented_overlapping_tiers_are_rejected():
    tiers = [
        {"from_amount": "0", "to_amount": "1000000", "rate": "0.7"},
        {"from_amount": "0", "to_amount": "1000000", "rate": "0.5"},
    ]
    items = [_item("rs_rate", tiers, "c-05", SAMPLE_B_QUOTE)]
    t = term(extract_terms("kb", _b_clauses(), FakeLLM(items)), TermKey.RS_RATE)
    assert t.status is TermStatus.NOT_FOUND


def test_tier_boundary_not_in_quote_is_rejected():
    clauses = split_clauses(
        "제1조 (수익배분)\n구간별 배분: 100만원 이하 50%, 100만원 초과 70%로 한다.\n제2조 (기간)\n1년으로 한다.\n"
    ).clauses
    tiers = [
        {"from_amount": "0", "to_amount": "2000000", "rate": "0.5"},
        {"from_amount": "2000000", "to_amount": None, "rate": "0.7"},
    ]
    items = [_item("rs_rate", tiers, "c-01", "100만원 이하 50%, 100만원 초과 70%로 한다.")]
    t = term(extract_terms("k4", clauses, FakeLLM(items)), TermKey.RS_RATE)
    assert t.status is TermStatus.NOT_FOUND


def test_tiers_with_a_gap_are_rejected():
    clauses = split_clauses(
        "제1조 (수익배분)\n100만원 이하 50%, 300만원 초과 70%로 한다.\n제2조 (기간)\n1년으로 한다.\n"
    ).clauses
    tiers = [
        {"from_amount": "0", "to_amount": "1000000", "rate": "0.5"},
        {"from_amount": "3000000", "to_amount": None, "rate": "0.7"},
    ]
    items = [_item("rs_rate", tiers, "c-01", "100만원 이하 50%, 300만원 초과 70%로 한다.")]
    assert (
        term(extract_terms("k5", clauses, FakeLLM(items)), TermKey.RS_RATE).status
        is TermStatus.NOT_FOUND
    )
