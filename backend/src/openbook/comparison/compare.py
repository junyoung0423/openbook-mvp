"""M3 표준계약서 비교.

LLM이 표준 조항마다 결과를 내면 코드가 아래를 검증한다. 통과하지 못한 '다른 지점'은 보여 주지 않고
'확인 필요'로 내려, 근거 없는 주장이 사용자에게 나가지 않게 한다.

- 대응 조항 id가 사용자 계약서에 실제로 있는가
- user_quote와 standard_quote가 각 원문에 글자 그대로 들어 있는가 (공백 차이는 무시)
- 설명 문장에 금지 표현이 없는가 (있으면 템플릿 문장으로 바꿈)
- 표준 조항마다 결과가 정확히 하나 있는가 (빠진 것은 '확인 필요')

'다른 지점을 찾지 못함'과 '대응 조항을 찾지 못함'에는 항상 안내 문구를 붙인다.
(찾지 못했다는 것이 표준과 같다는 뜻이 아니다.)

LLM 호출이 실패하면 LLMError가 그대로 올라간다. 호출한 쪽이 처리한다.
"""

from __future__ import annotations

import json
import re
from typing import Any

from openbook.comparison.models import (
    DISCLAIMER,
    ComparisonItem,
    ComparisonResult,
    StandardClause,
    Status,
)
from openbook.comparison.prompt import SYSTEM_PROMPT, build_user_prompt
from openbook.safety import is_clean
from openbook.schemas import Clause
from openbook.terms.llm import LLMClient

TEMPLATE_DIFFERENCE = "표준계약서와 다른 지점이 있습니다. 아래 두 원문을 비교해 확인하세요."


def compare_with_standard(
    contract_id: str,
    clauses: list[Clause],
    standard: list[StandardClause],
    llm: LLMClient,
) -> ComparisonResult:
    warnings: list[str] = []
    raw = llm.complete(SYSTEM_PROMPT, build_user_prompt(clauses, standard))
    answers = _parse(raw, warnings)
    by_id = {c.id: c for c in clauses}

    items = [_item(s, answers.get(s.id), by_id, warnings) for s in standard]
    return ComparisonResult(contract_id=contract_id, items=items, warnings=warnings)


# ---------------------------------------------------------------- parsing


def _parse(raw: str, warnings: list[str]) -> dict[str, dict[str, Any]]:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
    start, end = text.find("{"), text.rfind("}")
    try:
        data = json.loads(text[start : end + 1]) if 0 <= start < end else None
    except json.JSONDecodeError:
        data = None
    rows = data.get("comparisons") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        warnings.append("LLM 답을 읽지 못해 모든 표준 조항을 '확인 필요'로 두었습니다.")
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get("standard_id"), str):
            out.setdefault(row["standard_id"], row)  # 같은 id가 여러 번 오면 첫 번째만
    return out


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().strip("“”\"'‘’").strip()


# ---------------------------------------------------------------- per-clause


def _label(s: StandardClause) -> str:
    """경고 문구에 쓰는 표준 조항 이름 (내부 id 대신 '표준 제3조 자료 제공')."""
    name = " ".join(x for x in (s.no, s.title) if x)
    return f"표준 {name}" if name else f"표준 조항 {s.id}"


def _make(s: StandardClause, status: Status, **kw: Any) -> ComparisonItem:
    notice = None if status == "different" else DISCLAIMER
    return ComparisonItem(
        standard_id=s.id,
        standard_no=s.no,
        standard_title=s.title,
        core=s.core,
        status=status,
        notice=notice,
        **kw,
    )


def _item(
    s: StandardClause,
    row: dict[str, Any] | None,
    by_id: dict[str, Clause],
    warnings: list[str],
) -> ComparisonItem:
    if row is None:
        warnings.append(
            f"{_label(s)}: LLM 답에 이 표준 조항의 결과가 없어 '확인 필요'로 두었습니다."
        )
        return _make(s, "needs_check")

    status = row.get("status")
    if status == "not_found":
        return _make(s, "not_found")
    if status not in ("different", "none_detected"):
        warnings.append(f"{_label(s)}: 알 수 없는 status {status!r}라서 '확인 필요'로 두었습니다.")
        return _make(s, "needs_check")

    uid = row.get("user_clause_id")
    clause = by_id.get(uid) if isinstance(uid, str) else None
    if clause is None:
        warnings.append(
            f"{_label(s)}: 대응 조항 id {uid!r}가 사용자 계약서에 없어 '확인 필요'로 두었습니다."
        )
        return _make(s, "needs_check")

    if status == "none_detected":
        return _make(s, "none_detected", user_clause_id=clause.id)

    uq, sq = row.get("user_quote"), row.get("standard_quote")
    if not (isinstance(uq, str) and isinstance(sq, str) and _norm(uq) and _norm(sq)):
        warnings.append(
            f"{_label(s)}: 인용문이 없어 '다른 지점'을 보여 주지 않고 '확인 필요'로 두었습니다."
        )
        return _make(s, "needs_check", user_clause_id=clause.id)
    if _norm(uq) not in _norm(clause.text) or _norm(sq) not in _norm(s.text):
        warnings.append(f"{_label(s)}: 인용문이 원문에서 확인되지 않아 '확인 필요'로 두었습니다.")
        return _make(s, "needs_check", user_clause_id=clause.id)

    diff = row.get("difference")
    if not isinstance(diff, str) or not diff.strip() or not is_clean(diff):
        if isinstance(diff, str) and diff.strip():
            warnings.append(
                f"{_label(s)}: 설명 문장에 금지 표현이 있어 템플릿 문장으로 바꿨습니다."
            )
        diff = TEMPLATE_DIFFERENCE
    return _make(
        s,
        "different",
        user_clause_id=clause.id,
        difference=diff.strip(),
        user_quote=uq.strip(),
        standard_quote=sq.strip(),
    )
