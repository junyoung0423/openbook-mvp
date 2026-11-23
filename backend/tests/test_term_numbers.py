from decimal import Decimal

import pytest

from openbook.terms.numbers import find_amounts, find_rates, parse_korean_amount


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("5,000,000", 5_000_000),
        ("500만", 5_000_000),
        ("1억", 100_000_000),
        ("1억 5천만", 150_000_000),
        ("5천", 5_000),
        ("3백만", 3_000_000),
        ("만", 10_000),
        ("12,500", 12_500),
    ],
)
def test_parse_korean_amount(text, expected):
    assert parse_korean_amount(text) == Decimal(expected)


def test_find_amounts_various_notations():
    assert find_amounts("선급금 5,000,000원을 지급") == {Decimal(5_000_000)}
    assert find_amounts("계약금 500만원") == {Decimal(5_000_000)}
    assert find_amounts("1억 5천만원과 300만 원") == {Decimal(150_000_000), Decimal(3_000_000)}
    assert find_amounts("만원") == {Decimal(10_000)}


def test_find_amounts_ignores_days_and_dates():
    assert find_amounts("계약 체결일로부터 30일 이내, 2027년 1월 1일부터 2년") == set()


def test_find_amounts_does_not_read_hangul_numerals():
    # 한글 숫자는 읽지 못한다 → 근거 확인 실패 → 찾지 못함으로 처리된다 (틀린 값을 내지 않음)
    assert find_amounts("오백만 원") == set()
    assert find_amounts("일금 오백만원정") == set()  # 일부만 읽어 100만 원으로 오인하면 안 된다
    assert find_amounts("삼천원") == set()


def test_find_rates():
    assert find_rates("순매출의 60%로 한다") == {Decimal("0.6")}
    assert find_rates("60 %") == {Decimal("0.6")}
    assert find_rates("60퍼센트") == {Decimal("0.6")}
    assert find_rates("100분의 60") == {Decimal("0.6")}
    assert find_rates("12.5%") == {Decimal("0.125")}
    assert find_rates("총매출의 10%, 마케팅 5%") == {Decimal("0.1"), Decimal("0.05")}


def test_find_rates_none():
    assert find_rates("정산은 매월 말일") == set()
