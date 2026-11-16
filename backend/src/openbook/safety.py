"""사용자에게 보이는 문장의 금지 표현 필터.

서비스는 판단하지 않는다. 아래 표현이 들어간 문장은 쓰지 않고 호출한 쪽이 템플릿 문장으로 바꾼다.
(M3 비교 설명, M6 결과 문장, M7 Q&A 답변이 같은 필터를 쓴다.)

넓게 걸러 낸다: "유리"가 "유리창"에 걸리는 식의 오탐은 감수한다. 걸리면 안전한 템플릿 문장으로
바뀔 뿐이고, 못 걸러서 판단 표현이 나가는 것보다 낫다.
"""

from __future__ import annotations

BANNED_TERMS = ("위반", "부당", "불리", "유리", "위험도")


def find_banned(text: str) -> list[str]:
    """문장에 들어 있는 금지 표현 목록. 없으면 빈 목록."""
    return [t for t in BANNED_TERMS if t in text]


def is_clean(text: str) -> bool:
    return not find_banned(text)
