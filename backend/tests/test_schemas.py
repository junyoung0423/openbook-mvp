from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from openbook.schemas import Clause, ClauseSplitResult, Term, TermKey, TermSet, TermStatus


def extracted(key, value, **kw):
    return Term(
        key=key,
        value=value,
        status=TermStatus.EXTRACTED,
        source_clause_id="c-07",
        quote="계약서 원문",
        **kw,
    )


# ---- clauses


def test_clause_minimal():
    c = Clause(id="c-01", text="제1조 (목적) ...")
    assert c.type_id is None and c.std_clause_id is None


def test_duplicate_clause_ids_rejected():
    with pytest.raises(ValidationError):
        ClauseSplitResult(
            contract_id="k1",
            clauses=[Clause(id="c-01", text="a"), Clause(id="c-01", text="b")],
        )


# ---- terms


def test_money_and_rate_are_decimal():
    t = extracted(TermKey.MG_AMOUNT, "5000000")
    assert t.value == Decimal(5000000)
    r = extracted(TermKey.RS_RATE, "0.6")
    assert r.value == Decimal("0.6")


def test_rs_rate_over_one_rejected():
    with pytest.raises(ValidationError):
        extracted(TermKey.RS_RATE, "60")


def test_rs_rate_tiers():
    t = extracted(
        TermKey.RS_RATE,
        [
            {"from_amount": "0", "to_amount": "1000000", "rate": "0.5"},
            {"from_amount": "1000000", "rate": "0.7"},
        ],
    )
    assert len(t.value) == 2 and t.value[1].to_amount is None


def test_negative_money_rejected():
    with pytest.raises(ValidationError):
        extracted(TermKey.MG_AMOUNT, "-1")


def test_enum_value_checked():
    assert extracted(TermKey.REVENUE_BASE, "net").value.value == "net"
    with pytest.raises(ValidationError):
        extracted(TermKey.REVENUE_BASE, "profit")


def test_deduction_needs_exactly_one_of_rate_amount():
    ok = extracted(TermKey.DEDUCTIONS, [{"name": "결제수수료", "rate": "0.1"}])
    assert ok.value[0].rate == Decimal("0.1")
    with pytest.raises(ValidationError):
        extracted(TermKey.DEDUCTIONS, [{"name": "x", "rate": "0.1", "amount": "100"}])
    with pytest.raises(ValidationError):
        extracted(TermKey.DEDUCTIONS, [{"name": "x"}])


def test_extracted_requires_evidence():
    with pytest.raises(ValidationError):
        Term(key=TermKey.MG_AMOUNT, value="100", status=TermStatus.EXTRACTED)


def test_not_found_has_no_value_and_cannot_be_confirmed():
    t = Term(key=TermKey.MG_AMOUNT, status=TermStatus.NOT_FOUND)
    assert t.value is None
    with pytest.raises(ValidationError):
        Term(
            key=TermKey.MG_AMOUNT,
            status=TermStatus.NOT_FOUND,
            confirmed=True,
            confirmed_at=datetime.now(),
        )
    with pytest.raises(ValidationError):
        Term(key=TermKey.MG_AMOUNT, value="100", status=TermStatus.NOT_FOUND)


def test_user_input_needs_value_but_not_evidence():
    t = Term(key=TermKey.MG_AMOUNT, value="100", status=TermStatus.USER_INPUT)
    assert t.value == Decimal(100)
    with pytest.raises(ValidationError):
        Term(key=TermKey.MG_AMOUNT, status=TermStatus.USER_INPUT)


def test_confirmed_needs_timestamp():
    with pytest.raises(ValidationError):
        extracted(TermKey.MG_AMOUNT, "100", confirmed=True)
    t = extracted(TermKey.MG_AMOUNT, "100", confirmed=True, confirmed_at=datetime.now())
    assert t.confirmed


def test_termset_duplicate_keys_rejected():
    with pytest.raises(ValidationError):
        TermSet(
            contract_id="k1",
            terms=[extracted(TermKey.MG_AMOUNT, "1"), extracted(TermKey.MG_AMOUNT, "2")],
        )


def test_all_confirmed():
    now = datetime.now()
    a = extracted(TermKey.MG_AMOUNT, "1", confirmed=True, confirmed_at=now)
    b = extracted(TermKey.RS_RATE, "0.5")
    assert not TermSet(contract_id="k1", terms=[a, b]).all_confirmed
    assert not TermSet(contract_id="k1", terms=[]).all_confirmed
    b2 = extracted(TermKey.RS_RATE, "0.5", confirmed=True, confirmed_at=now)
    assert TermSet(contract_id="k1", terms=[a, b2]).all_confirmed


def test_json_roundtrip_serializes_decimal_as_string():
    t = extracted(TermKey.RS_RATE, "0.6")
    dumped = t.model_dump(mode="json")
    assert dumped["value"] == "0.6"
    assert Term.model_validate(dumped).value == Decimal("0.6")
