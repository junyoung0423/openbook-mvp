"""법령 근거 검색 (RAG). 법제처 Open API → 조문 단위 색인 → 글자 겹침 + 임베딩 검색."""

from openbook.law.embed import Embedder, EmbeddingError, UpstageEmbedder
from openbook.law.index import LawIndex, default_index
from openbook.law.lawgo import LawApiClient, LawApiError, parse_law
from openbook.law.models import LawArticle

__all__ = [
    "Embedder",
    "EmbeddingError",
    "LawApiClient",
    "LawApiError",
    "LawArticle",
    "LawIndex",
    "UpstageEmbedder",
    "default_index",
    "parse_law",
]
