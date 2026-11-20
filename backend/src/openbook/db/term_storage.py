"""공용 Term 스키마와 DB 행 사이의 안전한 변환."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from openbook.db.models import TermRecord
from openbook.schemas import Term, TermKey


def _contains_float(value: Any) -> bool:
    if isinstance(value, float):
        return True
    if isinstance(value, dict):
        return any(_contains_float(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_float(v) for v in value)
    return False


def scalar_numeric_value(term: Term) -> Decimal | None:
    if term.key is TermKey.MG_AMOUNT:
        return term.value
    if term.key is TermKey.RS_RATE and isinstance(term.value, Decimal):
        return term.value
    return None


def term_to_record(contract_id: str, term: Term) -> TermRecord:
    payload = term.model_dump(mode="json")
    value = payload["value"]
    if _contains_float(value):
        raise ValueError("terms.value에는 float를 저장할 수 없습니다.")
    return TermRecord(
        contract_id=contract_id,
        key=term.key.value,
        value=value,
        numeric_value=scalar_numeric_value(term),
        status=term.status.value,
        source_clause_id=term.source_clause_id,
        quote=term.quote,
        confirmed_at=term.confirmed_at if term.confirmed else None,
    )


def record_to_term(record: TermRecord) -> Term:
    """DB에서 읽은 값은 항상 공용 Term 모델로 재검증한다."""
    return Term.model_validate(
        {
            "key": record.key,
            "value": record.value,
            "status": record.status,
            "source_clause_id": record.source_clause_id,
            "quote": record.quote,
            "confirmed": record.confirmed_at is not None,
            "confirmed_at": record.confirmed_at,
        }
    )
