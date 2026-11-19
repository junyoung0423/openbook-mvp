"""M3 표준계약서 비교 (정준영). LLM이 표준 조항별로 다른 지점을 찾고 코드가 인용문을 검증한다."""

from openbook.comparison.compare import compare_with_standard
from openbook.comparison.models import (
    DISCLAIMER,
    ComparisonItem,
    ComparisonResult,
    StandardClause,
)
from openbook.comparison.standard import load_standard, standard_basis

__all__ = [
    "DISCLAIMER",
    "ComparisonItem",
    "ComparisonResult",
    "StandardClause",
    "compare_with_standard",
    "load_standard",
    "standard_basis",
]
