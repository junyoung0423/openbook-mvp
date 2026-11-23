"""M7 조항 Q&A: LLM 한 번 호출로 답과 근거 인용을 받고, 코드가 인용과 숫자를 검증한다.

검증
- 인용문은 해당 조항 원문에 글자 그대로 있어야 남는다. 확인된 인용이 하나도 없으면 '찾지 못함'.
- 답에 나온 숫자는 인용문·질문·조항 번호에 있는 숫자여야 한다. LLM이 계산한 숫자가 섞이면
  답 문장을 버리고 템플릿 문장으로 바꾼다 (금액 계산은 코드만 한다).
- 금지 표현이 있으면 템플릿 문장으로 바꾼다.
질문과 계약서 원문은 로그·경고에 넣지 않는다.
"""

from __future__ import annotations

import json
import re
from typing import Any

from openbook.comparison.models import StandardClause
from openbook.comparison.standard import load_standard, standard_basis
from openbook.law.models import LawArticle
from openbook.qa.models import (
    CALC_ANSWER,
    NOT_FOUND_ANSWER,
    TEMPLATE_ANSWER,
    Citation,
    QAResult,
)
from openbook.qa.prompt import SYSTEM_PROMPT, build_user_prompt
from openbook.quotes import quoted_in
from openbook.safety import is_clean
from openbook.schemas import Clause
from openbook.terms.llm import LLMClient

MAX_STANDARD = 4  # 프롬프트에 함께 넣는 표준 조항 수 (질문과 글자가 많이 겹치는 순)
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def answer_question(
    contract_id: str,
    question: str,
    clauses: list[Clause],
    llm: LLMClient,
    standard: list[StandardClause] | None = None,
    law: list[LawArticle] | None = None,
) -> QAResult:
    """질문에 계약서 조항을 근거로 답한다. LLMError는 호출한 쪽으로 올린다.

    law는 호출한 쪽이 법령 색인에서 미리 찾아 넘긴 조문이다 (없으면 법령 없이 답한다).
    """
    warnings: list[str] = []
    if standard is None:
        standard = load_standard()
    picked = _related_standard(question, standard)
    law = law or []

    raw = llm.complete(SYSTEM_PROMPT, build_user_prompt(question, clauses, picked, law))
    data = _parse(raw)
    if data is None:
        warnings.append("LLM 답을 읽지 못해 '찾지 못함'으로 두었습니다.")
        return _not_found(contract_id, question, warnings)

    citations = _verified_citations(data.get("citations"), clauses, picked, warnings, law)
    if not citations:
        return _not_found(contract_id, question, warnings)

    answer = data.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        answer = TEMPLATE_ANSWER
    elif not is_clean(answer):
        warnings.append("답 문장에 금지 표현이 있어 템플릿 문장으로 바꿨습니다.")
        answer = TEMPLATE_ANSWER
    elif not _numbers_supported(answer, question, citations, clauses, picked, law):
        warnings.append("답 문장에 원문에 없는 숫자가 있어 템플릿 문장으로 바꿨습니다.")
        answer = CALC_ANSWER

    basis = standard_basis() if any(c.source == "standard" for c in citations) else None
    return QAResult(
        contract_id=contract_id,
        question=question,
        found=True,
        answer=answer.strip(),
        citations=citations,
        basis=basis,
        warnings=warnings,
    )


# ---------------------------------------------------------------- helpers


def _not_found(contract_id: str, question: str, warnings: list[str]) -> QAResult:
    return QAResult(
        contract_id=contract_id,
        question=question,
        found=False,
        answer=NOT_FOUND_ANSWER,
        warnings=warnings,
    )


def _bigrams(s: str) -> set[str]:
    s = re.sub(r"\s+", "", s)
    return {s[i : i + 2] for i in range(len(s) - 1)}


def _related_standard(question: str, standard: list[StandardClause]) -> list[StandardClause]:
    """질문과 글자(2글자 묶음)가 많이 겹치는 표준 조항 몇 개. 겹침이 없으면 넣지 않는다."""
    q = _bigrams(question)
    scored = [
        (len(q & _bigrams(f"{s.title or ''} {s.text}")), i, s) for i, s in enumerate(standard)
    ]
    scored = [x for x in scored if x[0] > 0]
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [s for _, _, s in scored[:MAX_STANDARD]]


def _parse(raw: str) -> dict[str, Any] | None:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
    start, end = text.find("{"), text.rfind("}")
    try:
        data = json.loads(text[start : end + 1]) if 0 <= start < end else None
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _verified_citations(
    rows: Any,
    clauses: list[Clause],
    standard: list[StandardClause],
    warnings: list[str],
    law: list[LawArticle] | None = None,
) -> list[Citation]:
    by_id: dict[str, tuple[str, Clause | StandardClause | LawArticle]] = {
        c.id: ("contract", c) for c in clauses
    }
    by_id.update({s.id: ("standard", s) for s in standard})
    by_id.update({a.id: ("law", a) for a in law or []})
    out: list[Citation] = []
    dropped = 0
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        cid, quote = row.get("clause_id"), row.get("quote")
        hit = by_id.get(cid) if isinstance(cid, str) else None
        if hit is None or not isinstance(quote, str) or not quoted_in(quote, hit[1].text):
            dropped += 1
            continue
        source, c = hit
        if isinstance(c, LawArticle):
            out.append(
                Citation(
                    source="law",
                    clause_id=c.id,
                    clause_no=c.article_no,
                    clause_title=c.title,
                    quote=quote.strip(),
                    law_name=c.law_name,
                    effective_date=c.effective_date,
                    source_url=c.source_url,
                )
            )
            continue
        out.append(
            Citation(
                source=source,
                clause_id=c.id,
                clause_no=c.no,
                clause_title=c.title,
                quote=quote.strip(),
            )
        )
    if dropped:
        warnings.append(f"원문에서 확인되지 않은 인용 {dropped}개를 뺐습니다.")
    return out


def _numbers(s: str) -> set[str]:
    return {n.replace(",", "") for n in _NUMBER.findall(s)}


def _numbers_supported(
    answer: str,
    question: str,
    citations: list[Citation],
    clauses: list[Clause],
    standard: list[StandardClause],
    law: list[LawArticle] | None = None,
) -> bool:
    """답의 숫자가 모두 인용문·질문·조항 번호에서 온 것인가 (계산한 숫자를 막는다)."""
    allowed = _numbers(question)
    for c in citations:
        allowed |= _numbers(c.quote)
    for c in [*clauses, *standard]:
        allowed |= _numbers(c.no or "")
    for x in law or []:
        allowed |= _numbers(x.article_no)
    return _numbers(answer) <= allowed
