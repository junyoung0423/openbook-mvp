from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from openbook.schemas import Statement, StatementDraft, StatementField
from openbook.statements import MAX_CHARS, parse_pasted_statement

F = StatementField

# 모든 금액·항목은 가상의 값이다 (실제 정산서 아님)


def test_statement_schema_money_rules_and_period():
    s = Statement(
        period_start=date(2026, 10, 1),
        period_end=date(2026, 10, 31),
        gross="1000000",
        deductions=[{"name": "앱마켓 수수료", "amount": "300000"}],
        reported_payout="420000",
    )
    assert s.model_dump(mode="json")["gross"] == "1000000"
    with pytest.raises(ValidationError):
        Statement(
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 31),
            gross=1000000.0,  # float 거절
            reported_payout="0",
        )
    with pytest.raises(ValidationError):
        Statement(
            period_start=date(2026, 10, 31),
            period_end=date(2026, 10, 1),
            gross="1",
            reported_payout="0",
        )
    with pytest.raises(ValidationError):
        Statement(
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 31),
            gross="1",
            deductions=[{"name": " ", "amount": "1"}],
            reported_payout="0",
        )


def test_label_value_lines_from_excel():
    d = parse_pasted_statement(
        "정산 기간\t2026.10.01 ~ 2026.10.31\n"
        "총매출\t1,000,000\n"
        "앱마켓 수수료\t300,000\n"
        "결제 수수료\t30,000원\n"
        "지급액\t₩469,000\n"
    )
    assert (d.period_start, d.period_end) == (date(2026, 10, 1), date(2026, 10, 31))
    assert d.gross == Decimal(1000000) and d.reported_payout == Decimal(469000)
    assert [(x.name, x.amount) for x in d.deductions] == [
        ("앱마켓 수수료", Decimal(300000)),
        ("결제 수수료", Decimal(30000)),
    ]
    assert d.missing == [] and d.warnings == []
    assert all(r.field is not None for r in d.rows)


def test_colon_and_space_separated_lines_and_month_period():
    d = parse_pasted_statement(
        "2026년 10월 정산서\n정산월: 2026년 10월\n총 매출: 500,000원\n작가 지급액   200,000\n"
    )
    assert (d.period_start, d.period_end) == (date(2026, 10, 1), date(2026, 10, 31))
    assert d.gross == Decimal(500000) and d.reported_payout == Decimal(200000)
    assert d.missing == []


def test_horizontal_table_uses_single_row_or_total_row():
    one = parse_pasted_statement(
        "작품명\t총매출\t수수료\t지급액\n가상웹툰\t1,000,000\t300,000\t420,000"
    )
    assert one.gross == Decimal(1000000) and one.reported_payout == Decimal(420000)
    assert one.deductions[0].amount == Decimal(300000)
    assert one.missing == [F.PERIOD]

    many = parse_pasted_statement(
        "정산 기간: 2026-10\n"
        "회차\t판매액\t수수료\t지급액\n"
        "1화\t100,000\t30,000\t70,000\n"
        "2화\t200,000\t60,000\t140,000\n"
        "합계\t300,000\t90,000\t210,000\n"
    )
    assert many.gross == Decimal(300000) and many.reported_payout == Decimal(210000)
    assert many.period_start == date(2026, 10, 1)


def test_multiple_rows_without_total_are_not_summed():
    d = parse_pasted_statement("회차\t판매액\t지급액\n1화\t100,000\t70,000\n2화\t200,000\t140,000")
    assert d.gross is None and d.reported_payout is None  # 코드가 합계를 새로 만들지 않는다
    assert any("합계 줄" in w for w in d.warnings)


@pytest.mark.parametrize(
    "label",
    ["순매출", "수익배분금", "MG 차감", "선인세 회수", "원천징수세액", "미회수 잔액", "판매 건수"],
)
def test_ambiguous_rows_are_left_for_the_user(label):
    d = parse_pasted_statement(f"{label}\t123,000")
    assert d.gross is None and d.reported_payout is None and d.deductions == []
    assert d.rows[0].field is None and d.rows[0].note


def test_deduction_keywords_win_over_sales():
    d = parse_pasted_statement("판매 수수료\t10,000\n매출\t50,000")
    assert d.deductions[0].name == "판매 수수료" and d.gross == Decimal(50000)


def test_non_won_unit_blocks_all_amounts():
    d = parse_pasted_statement("(단위: 천원)\n총매출\t1,000\n지급액\t420")
    assert d.gross is None and d.reported_payout is None
    assert any("단위" in w for w in d.warnings)
    one = parse_pasted_statement("총매출(만원)\t100\n지급액\t420,000")
    assert one.gross is None and one.reported_payout == Decimal(420000)


def test_negative_numbers():
    d = parse_pasted_statement("총매출\t1,000\n환불 차감\t-200\n수수료\t(100)\n지급액\t△50")
    assert [x.amount for x in d.deductions] == [Decimal(200), Decimal(100)]
    assert d.reported_payout is None  # 음수 지급액은 넣지 않는다
    assert "음수" in (d.rows[-1].note or "")


def test_deduction_total_row_not_double_counted():
    d = parse_pasted_statement("수수료 A\t100\n수수료 B\t200\n공제 합계\t300")
    assert [x.amount for x in d.deductions] == [Decimal(100), Decimal(200)]
    only_total = parse_pasted_statement("공제 합계\t300")
    assert [x.amount for x in only_total.deductions] == [Decimal(300)]


def test_duplicate_field_keeps_first_and_warns_without_amounts():
    d = parse_pasted_statement("총매출\t1,000\n매출 합계\t2,000")
    assert d.gross == Decimal(1000)
    assert d.warnings and not any("2,000" in w or "매출" in w for w in d.warnings)


def test_bad_values_and_empty_input():
    d = parse_pasted_statement("정산 기간\t10월\n총매출\t약 백만 원")
    assert d.period_start is None and d.gross is None
    assert d.rows[0].note and d.rows[1].note
    empty = parse_pasted_statement("")
    assert empty.missing == [F.PERIOD, F.GROSS, F.REPORTED_PAYOUT]
    huge = parse_pasted_statement("x" * (MAX_CHARS + 1))
    assert huge.warnings and huge.rows == []


def test_draft_round_trips_as_json():
    d = parse_pasted_statement("정산 기간\t2026-10\n총매출\t1,000\n지급액\t600")
    again = StatementDraft.model_validate_json(d.model_dump_json())
    assert again == d and d.model_dump(mode="json")["gross"] == "1000"
