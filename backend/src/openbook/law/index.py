"""법령 조문 색인과 검색.

색인 파일(JSON)은 `python -m openbook.law build`로 만든다. 임베딩은 float16으로 줄여(base64) 저장해
파일이 약 6MB이고, Vercel 배포에 함께 실리도록 저장소에 넣는다 (법령 원문은 저작권 보호 대상이 아님,
저작권법 제7조). 파일이 없으면 법령 검색을 하지 않고 Q&A는 계약서·표준계약서만으로 답한다.

검색은 두 가지 순위를 섞는다 (Reciprocal Rank Fusion).
- 글자 겹침: 2글자 묶음 BM25. 흔한 묶음('저작', '하는')은 가볍게, 긴 조문(제2조 정의 등)은 덜 유리하게.
  조문 제목은 두 번 세어 제목이 맞는 조문을 앞으로 올린다. 법률 용어를 정확히 찾는 데 강하다.
- 임베딩: 질문(query)과 조문(passage)의 코사인 유사도. 표현이 달라도 뜻이 가까운 조문을 찾는다.

관련 없는 질문(예: 원천징수, MG 지급일)에는 법령을 붙이지 않는다.
- 임베딩이 있으면 가장 가까운 조문의 유사도가 RELEVANT_COSINE 미만일 때 빈 목록.
- 임베딩이 없거나 호출이 실패하면 글자 겹침만 쓰고, 최고 점수가 RELEVANT_BM25 미만일 때 빈 목록.
기준값은 질문 11개로 잰 값이다 (docs/design/law-rag.md).
"""

from __future__ import annotations

import base64
import json
import math
import os
import re
import struct
from collections import Counter
from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path

from openbook.law.embed import Embedder, EmbeddingError, cosine
from openbook.law.models import LawArticle

DEFAULT_INDEX = Path(__file__).resolve().parents[4] / "data" / "law" / "index.json"
RRF_K = 60  # RRF 상수 (흔히 쓰는 값)
TOP_K = 3  # 프롬프트에 넣는 조문 수
CANDIDATES = 20  # 각 방식에서 순위를 매길 후보 수
MIN_COSINE = 0.25  # 이보다 낮은 조문은 임베딩 후보에서 뺀다
RELEVANT_COSINE = (
    0.3  # 가장 가까운 조문이 이보다 낮으면 법령 없이 답한다 (관련 0.3~0.6, 무관 0.23 이하)
)
RELEVANT_BM25 = 10.0  # 임베딩 없이 찾을 때의 같은 기준 (관련 12~50, 무관 8 정도)
BM25_K1, BM25_B = 1.2, 0.75

# 작가가 쓰는 말 → 법령 용어. 질문에 왼쪽 말이 있으면 오른쪽 용어를 덧붙여 찾는다 (질문 확장).
# '작가→저작자', '웹툰→만화'는 넣지 않는다: 계산 질문(작가지급액)에 법령이 붙고 만화진흥법 질문이 흐려졌다.
# 평가 세트로 고른 목록이라 새 질문에도 통하는지는 따로 잰다 (docs/design/law-rag.md).
GLOSSARY = {
    "드라마": "영상화 영상저작물",
    "영화": "영상화 영상저작물",
    "애니메이션": "영상화 영상저작물",
    "영상": "영상화 영상저작물",
    "웹소설": "어문저작물",
    "남은 책": "복제물 배포",
    "재고": "복제물 배포",
    "끝난 뒤": "소멸 후",
    "끝나면": "소멸",
    "넘기": "양도",
    "넘어가": "양도",
    "고쳐": "변경 동일성",
    "이름": "성명표시",
    "허락": "이용허락",
    "마음대로": "일방적으로 결정 변경",
    "위약금": "손해배상액의 예정",
    "세금": "원천징수세율 소득세",
}


def expand_query(question: str) -> str:
    """질문에 법령 용어를 덧붙인다. 해당하는 말이 없으면 그대로."""
    extra = list(dict.fromkeys(v for k, v in GLOSSARY.items() if k in question))
    return f"{question} ({' '.join(extra)})" if extra else question


def bigrams(s: str) -> list[str]:
    """한글·영문·숫자만 남기고 2글자씩. 띄어쓰기·문장부호 차이를 무시한다."""
    s = re.sub(r"[^0-9A-Za-z가-힣]", "", s)
    return [s[i : i + 2] for i in range(len(s) - 1)]


class LawIndex:
    def __init__(
        self, articles: Sequence[LawArticle], vectors: Sequence[Sequence[float]] | None = None
    ) -> None:
        if vectors is not None and len(vectors) != len(articles):
            raise ValueError("조문 수와 임베딩 수가 다릅니다.")
        self.articles = list(articles)
        self.vectors = [list(v) for v in vectors] if vectors is not None else None
        self._grams = [
            Counter(bigrams(f"{a.law_name} {a.title or ''} {a.title or ''} {a.text}"))
            for a in self.articles
        ]
        self._len = [sum(g.values()) for g in self._grams]
        self._avg = (sum(self._len) / len(self._len)) if self._len else 1.0
        df = Counter(g for grams in self._grams for g in grams)
        n = len(self._grams)
        self._idf = {g: math.log(1 + (n - c + 0.5) / (c + 0.5)) for g, c in df.items()}

    # ------------------------------------------------------------ 파일

    @classmethod
    def load(cls, path: str | Path) -> LawIndex:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        articles = [LawArticle.model_validate(a) for a in data["articles"]]
        if "vectors_f16" in data:
            return cls(articles, unpack_vectors(data["vectors_f16"], data["dim"]))
        return cls(articles, data.get("vectors"))  # 예전 형식 (float 목록)

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data: dict = {"articles": [a.model_dump(mode="json") for a in self.articles]}
        if self.vectors:
            data["dim"] = len(self.vectors[0])
            data["vectors_f16"] = pack_vectors(self.vectors)
        p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    # ------------------------------------------------------------ 검색

    def keyword_scores(self, question: str) -> list[tuple[float, int]]:
        """BM25 점수 높은 순 (점수, 조문 번호). 겹치는 묶음이 없으면 빠진다."""
        q = set(bigrams(question))
        out = []
        for i, grams in enumerate(self._grams):
            norm = BM25_K1 * (1 - BM25_B + BM25_B * self._len[i] / self._avg)
            s = sum(
                self._idf[g] * grams[g] * (BM25_K1 + 1) / (grams[g] + norm) for g in q if g in grams
            )
            if s > 0:
                out.append((s, i))
        out.sort(key=lambda x: (-x[0], x[1]))
        return out[:CANDIDATES]

    def vector_scores(self, query_vector: Sequence[float]) -> list[tuple[float, int]]:
        """코사인 유사도 높은 순. MIN_COSINE 미만은 뺀다."""
        if not self.vectors:
            return []
        scored = [(cosine(query_vector, v), i) for i, v in enumerate(self.vectors)]
        scored = [x for x in scored if x[0] >= MIN_COSINE]
        scored.sort(key=lambda x: (-x[0], x[1]))
        return scored[:CANDIDATES]

    def keyword_ranking(self, question: str) -> list[int]:
        return [i for _, i in self.keyword_scores(question)]

    def vector_ranking(self, query_vector: Sequence[float]) -> list[int]:
        return [i for _, i in self.vector_scores(query_vector)]

    def search(
        self, question: str, embedder: Embedder | None = None, k: int = TOP_K
    ) -> list[LawArticle]:
        """관련 조문 최대 k개. 관련 있는 조문이 없으면 빈 목록 (법령 없이 답한다)."""
        question = expand_query(question)
        keyword = self.keyword_scores(question)
        vector: list[tuple[float, int]] | None = None
        if embedder is not None and self.vectors:
            try:
                vector = self.vector_scores(embedder.embed_query(question))
            except EmbeddingError:
                vector = None  # 글자 겹침만으로 찾는다
        if vector is not None:
            if not vector or vector[0][0] < RELEVANT_COSINE:
                return []
            rankings = [[i for _, i in keyword], [i for _, i in vector]]
        else:
            if not keyword or keyword[0][0] < RELEVANT_BM25:
                return []
            rankings = [[i for _, i in keyword]]
        score: dict[int, float] = {}
        for ranking in rankings:
            for rank, i in enumerate(ranking):
                score[i] = score.get(i, 0.0) + 1.0 / (RRF_K + rank + 1)
        best = sorted(score, key=lambda i: (-score[i], i))[:k]
        return [self.articles[i] for i in best]


def pack_vectors(vectors: Sequence[Sequence[float]]) -> str:
    """임베딩을 float16(리틀 엔디언)으로 이어 붙여 base64로. 코사인 순위에는 영향이 거의 없다."""
    flat = [x for v in vectors for x in v]
    return base64.b64encode(struct.pack(f"<{len(flat)}e", *flat)).decode("ascii")


def unpack_vectors(packed: str, dim: int) -> list[list[float]]:
    raw = base64.b64decode(packed)
    flat = struct.unpack(f"<{len(raw) // 2}e", raw)
    return [list(flat[i : i + dim]) for i in range(0, len(flat), dim)]


@lru_cache(maxsize=1)
def default_index() -> LawIndex | None:
    """LAW_INDEX_PATH(없으면 data/law/index.json). 파일이 없으면 None (법령 검색 끔)."""
    path = Path(os.environ.get("LAW_INDEX_PATH") or DEFAULT_INDEX)
    return LawIndex.load(path) if path.is_file() else None
