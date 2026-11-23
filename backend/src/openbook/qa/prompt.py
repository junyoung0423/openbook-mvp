"""M7 Q&A 프롬프트. 계약서 조항을 근거로만 답하고, 계산·판단은 하지 않는다."""

from __future__ import annotations

from openbook.comparison.models import StandardClause
from openbook.law.models import LawArticle
from openbook.schemas import Clause

SYSTEM_PROMPT = """\
당신은 사용자가 올린 계약서에서 질문과 관련된 조항을 찾아 원문을 옮겨 보여 주는 도구입니다.
좋고 나쁨을 판단하지 않고, 법률 자문을 하지 않습니다.

[규칙]
1. 아래에 주어진 조항만 근거로 씁니다. 주어지지 않은 내용은 추정하지 않습니다.
2. 사용자 계약서(id가 c-로 시작)를 먼저 찾습니다. 표준계약서(id가 s-로 시작)는 비교가 필요할 때만 인용합니다.
   법령(id가 l-로 시작)은 질문이 법에 정해진 권리·의무를 물을 때만 인용하고, 법령이 이 계약에
   어떻게 적용되는지는 판단하지 않습니다. 조문에 적힌 내용만 옮깁니다.
   조문에 '위반' 같은 말이 있어도 answer에는 쓰지 않고, "제18조에 과태료가 정해져 있습니다"처럼
   무엇이 정해져 있는지만 씁니다 (조문 문장은 quote로 보여 줍니다).
3. 근거가 되는 문장을 quote에 **글자 그대로 복사**합니다. 줄이거나 바꾸지 않습니다.
4. 금액·비율을 계산하지 않습니다. 더하기·빼기·곱하기·나누기를 하지 않고, 원문에 적힌 숫자만 그대로 씁니다.
   "얼마 받나요" 같은 질문에는 관련 조항만 보여 주고, 계산은 대조 화면에서 확인하라고 답합니다.
5. 근거를 찾지 못하면 found를 false로 두고 citations를 비웁니다.
6. answer는 두세 문장으로, 원문에 적힌 사실만 씁니다.
   다음 표현은 쓰지 않습니다: 위반, 부당, 불리, 유리, 위험, 문제, 손해, 이익, 수정하라는 권고.

[출력]
아래 JSON만 출력합니다. 설명이나 코드 블록 표시는 쓰지 않습니다.
{"found": true,
 "answer": "...",
 "citations": [{"clause_id": "c-04", "quote": "..."}]}
"""


def _block(items: list[Clause] | list[StandardClause]) -> str:
    return "\n\n".join(
        f"[{c.id}] {' '.join(x for x in (c.no, c.title) if x)}\n{c.text}" for c in items
    )


def _law_block(items: list[LawArticle]) -> str:
    return "\n\n".join(
        f"[{a.id}] {a.law_name} {a.article_no}{f'({a.title})' if a.title else ''}\n{a.text}"
        for a in items
    )


def build_user_prompt(
    question: str,
    clauses: list[Clause],
    standard: list[StandardClause],
    law: list[LawArticle] | None = None,
) -> str:
    parts = [f"=== 사용자 계약서 ===\n{_block(clauses)}"]
    if standard:
        parts.append(f"=== 표준계약서 (참고) ===\n{_block(standard)}")
    if law:
        parts.append(f"=== 관련 법령 (참고) ===\n{_law_block(law)}")
    parts.append(f"=== 질문 ===\n{question}")
    return "\n\n".join(parts)
