import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from openbook.schemas import (
    REQUIRED_TERM_KEYS,
    Clause,
    ClauseSplitResult,
    Term,
    TermKey,
    TermSet,
    TermStatus,
    termset_json_schema,
)


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
    # text는 제목 줄 없이 본문만 (제목은 no·title)
    c = Clause(id="c-01", no="제1조", title="목적", text="이 계약은 ...")
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
            confirmed_at=datetime.now(UTC),
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
    t = extracted(TermKey.MG_AMOUNT, "100", confirmed=True, confirmed_at=datetime.now(UTC))
    assert t.confirmed


def test_termset_duplicate_keys_rejected():
    with pytest.raises(ValidationError):
        TermSet(
            contract_id="k1",
            terms=[extracted(TermKey.MG_AMOUNT, "1"), extracted(TermKey.MG_AMOUNT, "2")],
        )


def _full_set(confirmed_keys=(), drop=()):
    """9개 key를 모두 갖춘 TermSet. confirmed_keys만 확정한다."""
    now = datetime.now(UTC)
    values = {
        TermKey.MG_AMOUNT: "5000000",
        TermKey.MG_RECOUP: "from_rs",
        TermKey.RS_RATE: "0.6",
        TermKey.REVENUE_BASE: "net",
        TermKey.DEDUCTIONS: [{"name": "결제 수수료", "rate": "0.1"}],
    }
    terms = []
    for k in TermKey:
        if k in drop:
            continue
        if k in values:
            c = k in confirmed_keys
            terms.append(extracted(k, values[k], confirmed=c, confirmed_at=now if c else None))
        else:
            terms.append(Term(key=k, status=TermStatus.NOT_FOUND))
    return TermSet(contract_id="k1", terms=terms)


def test_all_confirmed_needs_the_five_required_keys():
    assert not TermSet(contract_id="k1", terms=[]).all_confirmed
    partial = _full_set(confirmed_keys=REQUIRED_TERM_KEYS[:-1])
    assert not partial.all_confirmed
    assert partial.unconfirmed_required == [TermKey.DEDUCTIONS]
    # 필수가 아닌 4개가 찾지 못함이어도 필수 5개가 확정되면 열린다
    done = _full_set(confirmed_keys=REQUIRED_TERM_KEYS)
    assert done.all_confirmed and done.unconfirmed_required == []


def test_all_confirmed_false_when_a_key_is_missing():
    # 확정된 항목 하나만 있는 목록은 '전체 확정'이 아니다
    now = datetime.now(UTC)
    one = TermSet(
        contract_id="k1",
        terms=[extracted(TermKey.MG_AMOUNT, "1", confirmed=True, confirmed_at=now)],
    )
    assert not one.all_confirmed
    s = _full_set(confirmed_keys=REQUIRED_TERM_KEYS, drop=[TermKey.PAYMENT_DAY])
    assert s.missing_keys == [TermKey.PAYMENT_DAY] and not s.all_confirmed


def test_confirmed_at_without_confirmed_rejected():
    with pytest.raises(ValidationError):
        extracted(TermKey.MG_AMOUNT, "100", confirmed=False, confirmed_at=datetime.now(UTC))


@pytest.mark.parametrize("bad", [0.6, 1, 0.1 + 0.2, "1e7", "5,000,000", " 100", "-1", "NaN"])
def test_money_rejects_numbers_and_odd_text(bad):
    with pytest.raises(ValidationError):
        extracted(TermKey.MG_AMOUNT, bad)


@pytest.mark.parametrize("bad", [0.6, "60%", "1.5", ".6", "0.6 "])
def test_rate_rejects_numbers_and_odd_text(bad):
    with pytest.raises(ValidationError):
        extracted(TermKey.RS_RATE, bad)


def test_decimal_values_from_code_are_accepted_and_written_plainly():
    t = Term(key=TermKey.MG_AMOUNT, value=Decimal("1E+7"), status=TermStatus.USER_INPUT)
    assert t.model_dump(mode="json")["value"] == "10000000"


def test_blank_strings_are_not_evidence():
    with pytest.raises(ValidationError):
        extracted(TermKey.DEDUCTIONS, [{"name": "  ", "rate": "0.1"}])
    with pytest.raises(ValidationError):
        Term(
            key=TermKey.MG_AMOUNT,
            value="100",
            status=TermStatus.EXTRACTED,
            source_clause_id="c-01",
            quote="   ",
        )
    with pytest.raises(ValidationError):
        Term(
            key=TermKey.MG_AMOUNT,
            value="100",
            status=TermStatus.EXTRACTED,
            source_clause_id=" ",
            quote="원문",
        )


def test_json_roundtrip_serializes_decimal_as_string():
    t = extracted(TermKey.RS_RATE, "0.6")
    dumped = t.model_dump(mode="json")
    assert dumped["value"] == "0.6"
    assert Term.model_validate(dumped).value == Decimal("0.6")


# ---- JSON Schema (프론트 타입 생성용)


def test_json_schema_lists_value_type_per_key():
    schema = termset_json_schema()
    variants = {
        v["properties"]["key"]["const"]: v["properties"]["value"]
        for v in schema["$defs"]["Term"]["oneOf"]
    }
    assert set(variants) == {k.value for k in TermKey}
    assert {"$ref": "#/$defs/RevenueBase"} in variants["revenue_base"]["anyOf"]
    assert schema["$defs"]["RevenueBase"]["enum"] == ["gross", "net", "other"]
    rs_types = [s.get("type") for s in variants["rs_rate"]["anyOf"]]
    assert rs_types == ["string", "array", "null"]  # 비율 문자열 | 구간 목록 | 찾지 못함
    amount = schema["$defs"]["Deduction"]["properties"]["amount"]["anyOf"][0]
    assert amount["type"] == "string" and amount["pattern"]


def test_committed_json_schema_is_up_to_date():
    path = Path(__file__).resolve().parents[2] / "docs" / "schemas" / "terms.schema.json"
    committed = json.loads(path.read_text(encoding="utf-8"))
    assert committed == termset_json_schema(), (
        "스키마를 바꿨으면 python backend/scripts/export_json_schema.py를 실행해 커밋하세요."
    )
