"""원문 인용 검증. LLM이 낸 인용문이 원문에 글자 그대로 있는지 코드가 확인한다 (M3·M7 공통)."""

from __future__ import annotations

import re

_ELLIPSIS = re.compile(r"\s*(?:…|\.{3,})\s*")
_MIN_PIECE = 5  # 말줄임으로 나뉜 조각이 너무 짧으면 아무 곳에나 맞으므로 거절한다


def norm(s: str) -> str:
    """공백을 한 칸으로 줄이고 앞뒤 따옴표를 뗀다."""
    return re.sub(r"\s+", " ", s).strip().strip("“”\"'‘’").strip()


def quoted_in(quote: str, text: str) -> bool:
    """인용문이 원문에 글자 그대로 있는가 (공백 차이는 무시).

    LLM이 긴 문장을 '…'로 줄인 경우, 조각마다 원문에 그대로 있고 순서도 같아야 통과한다.
    """
    q, t = norm(quote), norm(text)
    if not q:
        return False
    if q in t:
        return True
    pieces = [p for p in _ELLIPSIS.split(q) if p]
    if len(pieces) < 2 or any(len(p) < _MIN_PIECE for p in pieces):
        return False
    pos = 0
    for p in pieces:
        pos = t.find(p, pos)
        if pos < 0:
            return False
        pos += len(p)
    return True
