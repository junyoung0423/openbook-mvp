"""공용 pydantic 스키마 (API·모듈 간 JSON 계약). 변경 시 프론트·백엔드 담당 모두 확인."""

from openbook.schemas.clauses import Clause, ClauseSplitResult
from openbook.schemas.statements import (
    PastedRow,
    Statement,
    StatementDeduction,
    StatementDraft,
    StatementField,
)
from openbook.schemas.terms import (
    REQUIRED_TERM_KEYS,
    Deduction,
    MgCarryover,
    MgRecoup,
    RevenueBase,
    RsTier,
    SettlementCycle,
    Term,
    TermKey,
    TermSet,
    TermStatus,
    termset_json_schema,
)

__all__ = [
    "REQUIRED_TERM_KEYS",
    "Clause",
    "ClauseSplitResult",
    "Deduction",
    "MgCarryover",
    "MgRecoup",
    "PastedRow",
    "RevenueBase",
    "RsTier",
    "SettlementCycle",
    "Statement",
    "StatementDeduction",
    "StatementDraft",
    "StatementField",
    "Term",
    "TermKey",
    "TermSet",
    "TermStatus",
    "termset_json_schema",
]
