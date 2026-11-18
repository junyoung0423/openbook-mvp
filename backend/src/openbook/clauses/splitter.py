"""M2 규칙 기반 조항 분할.

계약서 텍스트를 번호·제목 규칙으로 ``Clause`` 목록으로 나눈다. 규칙이 실패했다고 판단되는
문서는 ``needs_llm=True``로 표시해 LLM 보완 단계(별도 작업)가 맡게 한다. 이 모듈은 LLM을
부르지 않는다.

지원하는 형식
- article:  ``제7조 (제목)``, ``제7조 제목``, ``제7조의2``  (조 표기)
- numbered: ``7. 제목``                                      (조 표기가 없는 문서)

판단 원칙
- 제목 줄은 줄 맨 앞에서 시작해야 하고, 번호가 1부터 차례로 이어져야 한다.
  본문 속 "제5조에 따라" 같은 인용이나 호(1. 2.) 목록을 제목으로 오인하지 않기 위해서다.
- 조 표기 형식에서 차례를 벗어난 제목 후보가 있으면 조항을 놓쳤을 수 있으므로 LLM 보완 대상으로 둔다.
- 조항 원문(text)은 요약·수정 없이 원문 줄을 그대로 이어 붙인다. 제목 줄(``제7조 (제목)``,
  ``7. 제목``)은 no·title에 따로 담기므로 text에 넣지 않는다. 단 ``제7조(제목) 본문…``처럼
  제목 줄에 본문이 이어지면 그 본문은 text에 남긴다.
- 마지막 조항 뒤에 오는 작성일·서명 블록은 조항 본문이 아니므로 잘라 낸다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from openbook.schemas import Clause

Style = Literal["article", "numbered", "none"]

# 제7조 / 제7조의2, 뒤에는 공백·여는 괄호·줄 끝만 허용 ("제5조에 따라" 같은 인용 제외)
_ARTICLE = re.compile(r"^제\s*(\d+)\s*조(?:\s*의\s*(\d+))?(?=$|\s|[(（])\s*(.*)$")
_CHAPTER = re.compile(r"^제\s*\d+\s*장(?=$|\s)")
_NUMBERED = re.compile(r"^(\d{1,2})\.\s+(\S.*)$")
_PAREN_TITLE = re.compile(r"^[(（]\s*([^)）]*?)\s*[)）]")
_DATE_LINE = re.compile(r"^\d{4}\s*년\s*\d{1,2}\s*월\s*\d{1,2}\s*일\s*$")

# numbered 형식의 제목은 짧은 명사구여야 한다 (문장 목록 항목과 구별)
_MAX_NUMBERED_TITLE = 40
# 괄호 없는 조 제목이 이보다 길거나 마침표로 끝나면 제목이 아니라 본문으로 본다
_MAX_ARTICLE_TITLE = 30


class SplitOutcome(BaseModel):
    """분할 결과. needs_llm이 true이면 호출한 쪽이 LLM 보완을 이어서 해야 한다."""

    style: Style
    clauses: list[Clause] = Field(default_factory=list)
    needs_llm: bool = False
    warnings: list[str] = Field(default_factory=list)


@dataclass
class _Heading:
    line_idx: int
    no: str
    title: str | None
    order: tuple[int, int]  # (조 번호, 가지 번호), 가지 없으면 0
    body: str = ""  # 제목 줄에서 제목 뒤에 이어진 본문


def split_clauses(text: str, *, id_prefix: str = "c") -> SplitOutcome:
    """계약서 텍스트를 조항으로 나눈다."""
    lines = _normalize(text).split("\n")

    headings, rejected = _find_article_headings(lines)
    if len(headings) >= 2:
        warnings = [f"차례를 벗어난 제목 후보: {r}" for r in rejected]
        return _build("article", lines, headings, id_prefix, warnings)

    headings = _find_numbered_headings(lines)
    if len(headings) >= 2:
        return _build("numbered", lines, headings, id_prefix, [])

    return SplitOutcome(
        style="none",
        needs_llm=True,
        warnings=["조항 제목 규칙(제N조, N.)을 찾지 못했습니다."],
    )


# ---------------------------------------------------------------- headings


def _normalize(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("﻿", "")


def _find_article_headings(lines: list[str]) -> tuple[list[_Heading], list[str]]:
    found: list[_Heading] = []
    rejected: list[str] = []
    for i, raw in enumerate(lines):
        m = _ARTICLE.match(raw.strip())
        if not m:
            continue
        n, sub = int(m.group(1)), m.group(2)
        order = (n, int(sub) if sub else 0)
        if not _is_next(found[-1].order if found else None, order):
            rejected.append(raw.strip()[:30])
            continue
        no = f"제{n}조" + (f"의{sub}" if sub else "")
        title, body = _article_title(m.group(3))
        found.append(_Heading(i, no, title, order, body))
    return found, rejected


def _is_next(prev: tuple[int, int] | None, cur: tuple[int, int]) -> bool:
    if prev is None:
        return cur == (1, 0)
    pn, ps = prev
    n, s = cur
    if s == 0:
        return n == pn + 1
    return n == pn and s > ps  # 제7조의2, 제7조의3 ...


def _article_title(rest: str) -> tuple[str | None, str]:
    """제목 줄의 나머지에서 (제목, 이어진 본문)을 나눈다."""
    rest = rest.strip()
    if not rest:
        return None, ""
    m = _PAREN_TITLE.match(rest)
    if m:
        return m.group(1) or None, rest[m.end() :].strip()
    if len(rest) > _MAX_ARTICLE_TITLE or rest.endswith("."):
        return None, rest  # "제5조 을의 수익배분율은 …한다." 같은 본문
    return rest, ""


def _find_numbered_headings(lines: list[str]) -> list[_Heading]:
    found: list[_Heading] = []
    expected = 1
    for i, raw in enumerate(lines):
        m = _NUMBERED.match(raw.strip())
        if not m or int(m.group(1)) != expected:
            continue
        title = m.group(2).strip()
        if len(title) > _MAX_NUMBERED_TITLE or title.endswith("."):
            continue
        found.append(_Heading(i, str(expected), title, (expected, 0)))
        expected += 1
    return found


# ---------------------------------------------------------------- build


def _build(
    style: Style,
    lines: list[str],
    headings: list[_Heading],
    id_prefix: str,
    warnings: list[str],
) -> SplitOutcome:
    width = max(2, len(str(len(headings))))
    clauses: list[Clause] = []
    for k, h in enumerate(headings):
        end = headings[k + 1].line_idx if k + 1 < len(headings) else len(lines)
        # 제목 줄은 빼고, 제목 뒤에 이어진 본문만 남긴다
        chunk = [h.body, *lines[h.line_idx + 1 : end]]
        body = _clause_lines(chunk, last=k + 1 == len(headings))
        clauses.append(
            Clause(
                id=f"{id_prefix}-{k + 1:0{width}d}",
                no=h.no,
                title=h.title,
                text="\n".join(body).strip(),
            )
        )
    return SplitOutcome(
        style=style,
        clauses=clauses,
        needs_llm=bool(warnings),
        warnings=warnings,
    )


def _clause_lines(chunk: list[str], *, last: bool) -> list[str]:
    # 장(제N장) 제목 줄은 조항 본문이 아니다
    out = [ln for ln in chunk if not _CHAPTER.match(ln.strip())]
    if last:
        # 마지막 조항 뒤의 작성일·서명 블록은 잘라 낸다
        for i, ln in enumerate(out):
            if i > 0 and _DATE_LINE.match(ln.strip()):
                return out[:i]
    return out
