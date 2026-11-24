"""법령 검색 평가. data/law/eval.yaml의 질문마다 상위 k개 안에 정답 조문이 있는지 잰다.

- 정답이 있는 질문: 상위 k개 안에 정답 중 하나라도 있으면 맞음 (hit@k)
- 정답이 빈 질문(법령이 다루지 않는 질문): 검색 결과가 비어 있으면 맞음 (붙이지 않기)
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from openbook.law.embed import Embedder
from openbook.law.index import LawIndex
from openbook.law.models import LawArticle


def label(a: LawArticle) -> str:
    """평가 파일에 쓰는 조문 표기. 예: '저작권법 제22조'."""
    return f"{a.law_name} {a.article_no}"


@dataclass(frozen=True)
class EvalRow:
    question: str
    expect: tuple[str, ...]
    got: tuple[str, ...]

    @property
    def ok(self) -> bool:
        if not self.expect:
            return not self.got
        return any(g in self.expect for g in self.got)


@dataclass(frozen=True)
class EvalReport:
    rows: tuple[EvalRow, ...]

    def _rate(self, rows: Sequence[EvalRow]) -> float:
        return sum(r.ok for r in rows) / len(rows) if rows else 0.0

    @property
    def hit_rate(self) -> float:
        """정답이 있는 질문 중 상위 k개 안에 정답이 든 비율."""
        return self._rate([r for r in self.rows if r.expect])

    @property
    def abstain_rate(self) -> float:
        """법령이 다루지 않는 질문 중 아무것도 붙이지 않은 비율."""
        return self._rate([r for r in self.rows if not r.expect])


def unknown_labels(index: LawIndex, cases: Sequence[dict]) -> list[str]:
    """평가 파일의 정답 중 색인에 없는 조문 (오타·법령 개정 확인용)."""
    known = {label(a) for a in index.articles}
    return sorted({e for c in cases for e in c.get("expect") or [] if e not in known})


def evaluate(
    index: LawIndex, cases: Sequence[dict], embedder: Embedder | None = None
) -> EvalReport:
    rows = []
    for c in cases:
        got = tuple(label(a) for a in index.search(c["q"], embedder))
        rows.append(EvalRow(c["q"], tuple(c.get("expect") or ()), got))
    return EvalReport(tuple(rows))
