"""법령 조문 색인과 검색.

색인 파일(JSON)은 `python -m openbook.law build`로 만든다. 공개 법령이지만 크기가 커서(임베딩 포함)
저장소에는 넣지 않는다 (data/law/index.json은 .gitignore). 파일이 없으면 법령 검색을 하지 않고
Q&A는 지금처럼 계약서·표준계약서만으로 답한다.

검색은 두 가지 순위를 섞는다 (Reciprocal Rank Fusion).
- 글자 겹침: 질문과 조문의 2글자 묶음이 겹치는 수. 조문 번호·법률 용어를 정확히 찾는 데 강하다.
- 임베딩: 질문(query)과 조문(passage)의 코사인 유사도. 표현이 달라도 뜻이 가까운 조문을 찾는다.
임베딩이 없거나 호출이 실패하면 글자 겹침만 쓴다.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path

from openbook.law.embed import Embedder, EmbeddingError, cosine
from openbook.law.models import LawArticle

DEFAULT_INDEX = Path(__file__).resolve().parents[4] / "data" / "law" / "index.json"
RRF_K = 60  # RRF 상수 (흔히 쓰는 값)
TOP_K = 3  # 프롬프트에 넣는 조문 수
CANDIDATES = 20  # 각 방식에서 순위를 매길 후보 수
MIN_COSINE = (
    0.2  # 이보다 낮으면 임베딩 후보에서 뺀다 (뜻이 거의 무관). 관련 문장 0.3대, 무관 0.1 아래
)


def bigrams(s: str) -> set[str]:
    s = re.sub(r"\s+", "", s)
    return {s[i : i + 2] for i in range(len(s) - 1)}


class LawIndex:
    def __init__(
        self, articles: Sequence[LawArticle], vectors: Sequence[Sequence[float]] | None = None
    ) -> None:
        if vectors is not None and len(vectors) != len(articles):
            raise ValueError("조문 수와 임베딩 수가 다릅니다.")
        self.articles = list(articles)
        self.vectors = [list(v) for v in vectors] if vectors is not None else None
        self._grams = [bigrams(f"{a.law_name} {a.title or ''} {a.text}") for a in self.articles]

    # ------------------------------------------------------------ 파일

    @classmethod
    def load(cls, path: str | Path) -> LawIndex:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        articles = [LawArticle.model_validate(a) for a in data["articles"]]
        return cls(articles, data.get("vectors"))

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "articles": [a.model_dump(mode="json") for a in self.articles],
            "vectors": self.vectors,
        }
        p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    # ------------------------------------------------------------ 검색

    def keyword_ranking(self, question: str) -> list[int]:
        q = bigrams(question)
        scored = [(len(q & g), i) for i, g in enumerate(self._grams)]
        scored = [x for x in scored if x[0] > 0]
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [i for _, i in scored[:CANDIDATES]]

    def vector_ranking(self, query_vector: Sequence[float]) -> list[int]:
        if not self.vectors:
            return []
        scored = [(cosine(query_vector, v), i) for i, v in enumerate(self.vectors)]
        scored = [x for x in scored if x[0] >= MIN_COSINE]
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [i for _, i in scored[:CANDIDATES]]

    def search(
        self, question: str, embedder: Embedder | None = None, k: int = TOP_K
    ) -> list[LawArticle]:
        rankings = [self.keyword_ranking(question)]
        if embedder is not None and self.vectors:
            try:
                rankings.append(self.vector_ranking(embedder.embed_query(question)))
            except EmbeddingError:
                pass  # 글자 겹침만으로 찾는다
        score: dict[int, float] = {}
        for ranking in rankings:
            for rank, i in enumerate(ranking):
                score[i] = score.get(i, 0.0) + 1.0 / (RRF_K + rank + 1)
        best = sorted(score, key=lambda i: (-score[i], i))[:k]
        return [self.articles[i] for i in best]


@lru_cache(maxsize=1)
def default_index() -> LawIndex | None:
    """LAW_INDEX_PATH(없으면 data/law/index.json). 파일이 없으면 None (법령 검색 끔)."""
    path = Path(os.environ.get("LAW_INDEX_PATH") or DEFAULT_INDEX)
    return LawIndex.load(path) if path.is_file() else None
