"""문장 임베딩. Upstage Embeddings API (OpenAI 호환 /embeddings).

- 조문은 passage 모델, 질문은 query 모델로 임베딩한다 (같은 벡터 공간).
- UPSTAGE_EMBEDDING_PASSAGE_MODEL (기본 embedding-passage)
- UPSTAGE_EMBEDDING_QUERY_MODEL   (기본 embedding-query)
질문 원문은 로그·오류에 넣지 않는다.
"""

from __future__ import annotations

import math
import os
from collections.abc import Sequence
from typing import Protocol

import httpx
from dotenv import load_dotenv

from openbook.terms.llm import DEFAULT_BASE_URL

BATCH = 50


class EmbeddingError(RuntimeError):
    """임베딩 호출 실패. 메시지에 입력 문장을 넣지 않는다."""


class Embedder(Protocol):
    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class UpstageEmbedder:
    def __init__(
        self,
        api_key: str,
        passage_model: str = "embedding-passage",
        query_model: str = "embedding-query",
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
    ) -> None:
        if not api_key:
            raise ValueError("UPSTAGE_API_KEY가 비어 있습니다.")
        self._key = api_key
        self._passage = passage_model
        self._query = query_model
        self._url = base_url.rstrip("/") + "/embeddings"
        self._timeout = timeout

    @classmethod
    def from_env(cls) -> UpstageEmbedder:
        load_dotenv()
        return cls(
            api_key=os.environ.get("UPSTAGE_API_KEY", ""),
            passage_model=os.environ.get("UPSTAGE_EMBEDDING_PASSAGE_MODEL", "embedding-passage"),
            query_model=os.environ.get("UPSTAGE_EMBEDDING_QUERY_MODEL", "embedding-query"),
            base_url=os.environ.get("UPSTAGE_BASE_URL", DEFAULT_BASE_URL),
        )

    def _call(self, model: str, texts: Sequence[str]) -> list[list[float]]:
        try:
            resp = httpx.post(
                self._url,
                headers={"Authorization": f"Bearer {self._key}"},
                json={"model": model, "input": list(texts)},
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise EmbeddingError(f"임베딩 연결 실패 ({type(exc).__name__})") from exc
        if resp.status_code != 200:
            raise EmbeddingError(f"임베딩 호출 실패: HTTP {resp.status_code}")
        try:
            rows = sorted(resp.json()["data"], key=lambda r: r["index"])
            return [[float(v) for v in r["embedding"]] for r in rows]
        except (ValueError, KeyError, TypeError) as exc:
            raise EmbeddingError("임베딩 응답 형식이 예상과 다릅니다.") from exc

    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), BATCH):
            out.extend(self._call(self._passage, texts[i : i + BATCH]))
        return out

    def embed_query(self, text: str) -> list[float]:
        return self._call(self._query, [text])[0]


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0
