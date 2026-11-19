"""M4 MG·RS 조건 추출 (정준영, 검증 박다연). LLM 구조화 출력 + 코드 검증기. 근거 조항 인용 필수, 못 찾으면 not_found."""

from openbook.terms.extractor import ExtractionResult, extract_terms
from openbook.terms.llm import LLMClient, UpstageClient

__all__ = ["ExtractionResult", "LLMClient", "UpstageClient", "extract_terms"]
