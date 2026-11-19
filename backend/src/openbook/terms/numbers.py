"""근거 문장에서 금액·비율을 읽어 내는 코드.

LLM이 낸 값(예: mg_amount=5000000)이 인용한 계약서 문장 안에 실제로 적혀 있는지 대조할 때 쓴다.
읽지 못하는 표기(예: "오백만 원" 같은 한글 숫자)는 빈 결과를 돌려주고, 호출한 쪽은 그것을
'근거로 확인하지 못함'으로 취급한다. 틀린 값을 내는 것보다 찾지 못함으로 두는 쪽이 낫다는 원칙이다.
금액·비율은 모두 Decimal로 다룬다.
"""

from __future__ import annotations

import re
from decimal import Decimal

_NUM = r"\d[\d,]*(?:\.\d+)?"
_UNIT = r"[천백십만억]"
# 숫자·단위가 이어진 덩어리 뒤에 '원'이 오는 경우: 5,000,000원 / 500만원 / 1억 5천만원 / 만원
# 앞에 한글 숫자·단위가 붙어 있으면(예: "오백만 원") 일부만 읽어 틀린 금액이 나오므로 읽지 않는다.
_WON = re.compile(
    rf"(?<![일이삼사오육칠팔구영공천백십만억])((?:{_NUM}|{_UNIT})(?:\s*(?:{_NUM}|{_UNIT}))*)\s*원"
)
_TOKEN = re.compile(rf"{_NUM}|{_UNIT}")
_PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s*(?:%|퍼센트|프로)")
_BUNSUI = re.compile(r"100\s*분의\s*(\d+(?:\.\d+)?)")

_SMALL = {"천": 1_000, "백": 100, "십": 10}
_BIG = {"만": 10_000, "억": 100_000_000}


def parse_korean_amount(s: str) -> Decimal:
    """'5,000,000' '500만' '1억 5천만' '만' 같은 문자열을 원 단위 금액으로 바꾼다."""
    total = Decimal(0)
    section = Decimal(0)
    num: Decimal | None = None
    for t in _TOKEN.findall(s):
        if t[0].isdigit():
            num = Decimal(t.replace(",", ""))
        elif t in _SMALL:
            section += (num if num is not None else Decimal(1)) * _SMALL[t]
            num = None
        else:
            val = section + (num or Decimal(0))
            if val == 0:
                val = Decimal(1)
            total += val * _BIG[t]
            section = Decimal(0)
            num = None
    return total + section + (num or Decimal(0))


def find_amounts(text: str) -> set[Decimal]:
    """문장 안의 '○○원' 금액을 모두 찾는다."""
    return {parse_korean_amount(m.group(1)) for m in _WON.finditer(text)}


def find_rates(text: str) -> set[Decimal]:
    """문장 안의 비율을 0~1 소수로 모두 찾는다. '60%', '60퍼센트', '100분의 60' 지원."""
    rates = {Decimal(m.group(1)) / 100 for m in _PERCENT.finditer(text)}
    rates |= {Decimal(m.group(1)) / 100 for m in _BUNSUI.finditer(text)}
    return rates
