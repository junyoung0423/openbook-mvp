"""M4 MG·RS 조건 추출.

LLM이 낸 값은 그대로 쓰지 않고 코드가 아래 순서로 다시 검증한다. 하나라도 통과하지 못하면
그 항목은 값을 버리고 '찾지 못함(not_found)'으로 둔다. 틀린 값을 내는 것보다 낫다는 원칙이다.

1. 형식: 스키마(Term)를 통과하는가 (금액 0 이상, 비율 0~1, 선택값 목록 등)
2. 근거 인용: quote가 계약서 조항 원문에 글자 그대로 들어 있는가 (공백 차이는 무시)
3. 숫자 대조: 금액·비율 값이 quote 안에 실제로 적혀 있는가

결과의 모든 조건은 confirmed=False다. 확정은 사용자만 한다.
"""

from __future__ import annotations

import itertools
import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from openbook.schemas import Clause, Deduction, RsTier, Term, TermKey, TermSet, TermStatus
from openbook.terms.llm import LLMClient
from openbook.terms.numbers import find_amounts, find_rates
from openbook.terms.prompt import SYSTEM_PROMPT, build_user_prompt


class ExtractionResult(BaseModel):
    terms: TermSet
    warnings: list[str] = Field(default_factory=list)


def extract_terms(contract_id: str, clauses: list[Clause], llm: LLMClient) -> ExtractionResult:
    """조항 목록에서 MG·RS 조건 9개 항목을 추출한다. 항상 9개 항목을 모두 돌려준다."""
    warnings: list[str] = []
    raw = llm.complete(SYSTEM_PROMPT, build_user_prompt(clauses))

    items = _parse_items(raw, warnings)
    by_id = {c.id: c for c in clauses}

    terms: list[Term] = []
    for key in TermKey:
        item = items.get(key.value)
        terms.append(_verify(key, item, by_id, clauses, warnings))
    return ExtractionResult(terms=TermSet(contract_id=contract_id, terms=terms), warnings=warnings)


# ---------------------------------------------------------------- parsing


def _parse_items(raw: str, warnings: list[str]) -> dict[str, dict[str, Any]]:
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)  # 코드 블록 표시 제거
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        warnings.append("LLM 답이 JSON이 아니어서 모든 항목을 찾지 못함으로 처리했습니다.")
        return {}
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        warnings.append("LLM 답의 JSON을 읽지 못해 모든 항목을 찾지 못함으로 처리했습니다.")
        return {}

    raw_items = data.get("terms") if isinstance(data, dict) else None
    if not isinstance(raw_items, list):
        warnings.append("LLM 답에 terms 목록이 없어 모든 항목을 찾지 못함으로 처리했습니다.")
        return {}

    valid_keys = {k.value for k in TermKey}
    items: dict[str, dict[str, Any]] = {}
    for it in raw_items:
        if not isinstance(it, dict):
            continue
        key = it.get("key")
        if key not in valid_keys:
            warnings.append(f"알 수 없는 항목 key를 무시했습니다: {key!r}")
            continue
        items.setdefault(key, it)  # 같은 key가 여러 번 오면 첫 번째만 쓴다
    return items


# ---------------------------------------------------------------- verification


def _norm(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return s.strip("“”\"'‘’").strip()


def _not_found(key: TermKey, warnings: list[str], reason: str | None = None) -> Term:
    if reason:
        warnings.append(f"{key.value}: {reason}")
    return Term(key=key, status=TermStatus.NOT_FOUND)


def _verify(
    key: TermKey,
    item: dict[str, Any] | None,
    by_id: dict[str, Clause],
    clauses: list[Clause],
    warnings: list[str],
) -> Term:
    if item is None or item.get("value") in (None, "", []):
        return _not_found(key, warnings)

    quote = item.get("quote")
    if not isinstance(quote, str) or not _norm(quote):
        return _not_found(key, warnings, "근거 인용(quote)이 없어 값을 쓰지 않았습니다.")
    q = _norm(quote)

    clause_id = item.get("clause_id")
    clause = by_id.get(clause_id) if isinstance(clause_id, str) else None
    if clause is None or q not in _norm(clause.text):
        # 조항 번호를 잘못 적었을 수 있다: 인용문이 정확히 한 조항에만 있으면 그쪽으로 바로잡는다
        hits = [c for c in clauses if q in _norm(c.text)]
        if len(hits) != 1:
            return _not_found(
                key, warnings, "인용문이 계약서 원문에서 확인되지 않아 값을 쓰지 않았습니다."
            )
        if clause is not None or clause_id:
            warnings.append(
                f"{key.value}: 근거 조항 번호를 {clause_id!r}에서 {hits[0].id!r}로 바로잡았습니다."
            )
        clause = hits[0]

    value, notes = _normalize_value(key, item["value"])
    warnings.extend(f"{key.value}: {n}" for n in notes)
    if _is_empty(value) or value == []:
        return _not_found(key, warnings, "정량화된 값이 없어 쓰지 않았습니다.")

    try:
        term = Term(
            key=key,
            value=value,
            status=TermStatus.EXTRACTED,
            source_clause_id=clause.id,
            quote=quote.strip(),
        )
    except ValidationError:
        return _not_found(key, warnings, "값의 형식이 스키마와 맞지 않아 쓰지 않았습니다.")

    if not _supported_by_quote(term, q):
        return _not_found(key, warnings, "값이 인용문에서 확인되지 않아 쓰지 않았습니다.")
    return term


def _is_empty(x: Any) -> bool:
    return x is None or (isinstance(x, str) and not x.strip())


def _normalize_value(key: TermKey, value: Any) -> tuple[Any, list[str]]:
    """LLM이 자주 내는 모양을 스키마가 받는 모양으로 정리한다. 의미를 바꾸지는 않는다.

    - 값이 JSON 문자열로 한 번 더 감싸져 오면("[{...}]") 풀어 준다.
    - 구간이 하나뿐이고 0원부터 끝없이 이어지는 RS 구간표는 단일 비율로 바꾼다.
    - 비율도 금액도 없는 공제 항목(예: "을이 동의한 금액")은 계산에 쓸 수 없으므로 빼고,
      어떤 항목을 뺐는지 알려 사용자가 확인하게 한다.
    """
    notes: list[str] = []
    if (
        key in (TermKey.RS_RATE, TermKey.DEDUCTIONS)
        and isinstance(value, str)
        and value.strip()[:1] in ("[", "{")
    ):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return value, notes  # 스키마 검증에서 걸러진다

    if key is TermKey.RS_RATE and isinstance(value, list):
        if not all(isinstance(t, dict) for t in value):
            return value, notes
        tiers = []
        for t in value:
            t = dict(t)
            t["from_amount"] = "0" if _is_empty(t.get("from_amount")) else t["from_amount"]
            t["to_amount"] = None if _is_empty(t.get("to_amount")) else t["to_amount"]
            tiers.append(t)
        if len(tiers) == 1 and tiers[0]["to_amount"] is None:
            try:
                if Decimal(str(tiers[0]["from_amount"])) == 0:
                    return tiers[0].get("rate"), notes
            except InvalidOperation:
                pass
        return tiers, notes

    if key is TermKey.DEDUCTIONS and isinstance(value, list):
        if not all(isinstance(d, dict) for d in value):
            return value, notes
        kept, dropped = [], []
        for d in value:
            rate = None if _is_empty(d.get("rate")) else d["rate"]
            amount = None if _is_empty(d.get("amount")) else d["amount"]
            if rate is None and amount is None:
                dropped.append(str(d.get("name") or "이름 없음"))
            else:
                kept.append({"name": d.get("name"), "rate": rate, "amount": amount})
        if dropped:
            notes.append(
                "비율·금액이 정해지지 않은 공제 항목은 계산에 쓸 수 없어 뺐습니다. "
                f"계약서를 확인해 직접 입력하세요: {', '.join(dropped)}"
            )
        return kept, notes

    return value, notes


def _tiers_supported(tiers: list[Any], amounts: set[Decimal], rates: set[Decimal]) -> bool:
    """구간별 RS: 구간이 0원부터 겹침·빈틈 없이 이어지고, 비율과 경계 금액이 모두 인용문에 있어야 한다."""
    if not tiers or not all(isinstance(t, RsTier) for t in tiers):
        return False
    ordered = sorted(tiers, key=lambda t: t.from_amount)
    if ordered[0].from_amount != 0:
        return False
    for prev, cur in itertools.pairwise(ordered):
        if prev.to_amount is None or prev.to_amount != cur.from_amount:
            return False
    for t in ordered:
        if t.rate not in rates:
            return False
        if t.from_amount != 0 and t.from_amount not in amounts:
            return False
        if t.to_amount is not None and t.to_amount not in amounts:
            return False
    return True


def _supported_by_quote(term: Term, quote: str) -> bool:
    """금액·비율 값이 인용문에 실제로 적혀 있는지 본다. 숫자가 없는 항목은 인용문 존재로 충분하다."""
    amounts, rates = find_amounts(quote), find_rates(quote)
    v = term.value
    if term.key is TermKey.MG_AMOUNT:
        return v in amounts
    if term.key is TermKey.RS_RATE:
        if isinstance(v, Decimal):
            return v in rates
        return _tiers_supported(v, amounts, rates)
    if term.key is TermKey.DEDUCTIONS:
        return all(
            isinstance(d, Deduction)
            and (
                (d.rate is not None and d.rate in rates)
                or (d.amount is not None and d.amount in amounts)
            )
            for d in v
        )
    return True
