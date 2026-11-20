"""GET, PUT /contracts/{id}/terms: MG·RS 조건 조회, 수정·확정 (정준영).

규칙
- 확정은 사용자 요청으로만 기록한다. confirmed_at은 서버 시각으로 정한다 (요청 값을 믿지 않음).
- 값을 바꾸면 상태가 '직접 입력'(user_input)이 된다. 근거 조항·인용은 화면에서 원문을 보여 줄 수
  있게 그대로 둔다.
- 필수 5개가 모두 확정되면 계약서 상태를 '확정', 아니면 '조건 확인 대기'로 둔다 ('처리중'이면 그대로).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field, ValidationError, model_validator
from sqlalchemy import select

from openbook.api.deps import DB, OwnedContract, api_error
from openbook.db import Contract, TermRecord, record_to_term, term_to_record
from openbook.schemas import Term, TermKey, TermSet, TermStatus

router = APIRouter(tags=["terms"])

STATUS_PROCESSING = "처리중"
STATUS_WAITING = "조건 확인 대기"
STATUS_CONFIRMED = "확정"


class TermsResponse(BaseModel):
    """GET·PUT 응답. 화면은 unconfirmed_required로 '확인해 주세요' 표시를 한다."""

    contract_id: str
    terms: list[Term]
    missing_keys: list[TermKey]
    unconfirmed_required: list[TermKey]
    all_confirmed: bool = Field(description="true면 정산서 대조를 열 수 있다")

    @classmethod
    def of(cls, ts: TermSet) -> TermsResponse:
        return cls(
            contract_id=ts.contract_id,
            terms=ts.terms,
            missing_keys=ts.missing_keys,
            unconfirmed_required=ts.unconfirmed_required,
            all_confirmed=ts.all_confirmed,
        )


class TermUpdate(BaseModel):
    key: TermKey
    value: Any = Field(
        default=None,
        description="새 값 (key별 형식, 금액·비율은 문자열). null이면 값을 바꾸지 않는다",
    )
    confirmed: bool = Field(description="true=확정, false=확정 취소")


class TermsUpdate(BaseModel):
    """PUT 본문. 보낸 key만 바꾼다."""

    terms: list[TermUpdate] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique(self) -> TermsUpdate:
        keys = [t.key for t in self.terms]
        if len(keys) != len(set(keys)):
            raise ValueError("같은 key를 두 번 보냈습니다.")
        return self


def _records(db: DB, contract_id: str) -> dict[str, TermRecord]:
    rows = db.scalars(select(TermRecord).where(TermRecord.contract_id == contract_id)).all()
    return {r.key: r for r in rows}


def _term_set(contract_id: str, records: dict[str, TermRecord]) -> TermSet:
    order = {k.value: i for i, k in enumerate(TermKey)}
    terms = [record_to_term(r) for r in sorted(records.values(), key=lambda r: order[r.key])]
    return TermSet(contract_id=contract_id, terms=terms)


def _json_value(term: Term) -> Any:
    return term.model_dump(mode="json")["value"]


def _invalid(key: TermKey, exc: ValidationError) -> Exception:
    msg = exc.errors()[0]["msg"].removeprefix("Value error, ")
    return api_error(422, "INVALID_TERM", f"{key.value}: {msg}")


@router.get("/contracts/{contract_id}/terms", response_model=TermsResponse)
def get_terms(contract: OwnedContract, db: DB) -> TermsResponse:
    return TermsResponse.of(_term_set(contract.id, _records(db, contract.id)))


@router.put("/contracts/{contract_id}/terms", response_model=TermsResponse)
def put_terms(body: TermsUpdate, contract: OwnedContract, db: DB) -> TermsResponse:
    records = _records(db, contract.id)
    now = datetime.now(UTC)
    for u in body.terms:
        rec = records.get(u.key.value)
        old = record_to_term(rec) if rec else None
        data: dict[str, Any] = (
            old.model_dump() if old else {"key": u.key, "status": TermStatus.NOT_FOUND}
        )
        try:
            if u.value is not None:
                new = Term(key=u.key, value=u.value, status=TermStatus.USER_INPUT)
                if old is None or old.value is None or _json_value(old) != _json_value(new):
                    data.update(value=new.value, status=TermStatus.USER_INPUT)
            keep_time = (
                u.confirmed and old is not None and old.confirmed and data["value"] == old.value
            )
            data["confirmed"] = u.confirmed
            data["confirmed_at"] = (old.confirmed_at if keep_time else now) if u.confirmed else None
            term = Term.model_validate(data)
        except ValidationError as exc:
            db.rollback()
            raise _invalid(u.key, exc) from None

        fresh = term_to_record(contract.id, term)
        if rec is None:
            db.add(fresh)
            records[u.key.value] = fresh
        else:
            for attr in ("value", "numeric_value", "status", "source_clause_id", "quote"):
                setattr(rec, attr, getattr(fresh, attr))
            rec.confirmed_at = fresh.confirmed_at

    ts = _term_set(contract.id, records)
    _update_status(contract, ts)
    db.commit()
    return TermsResponse.of(ts)


def _update_status(contract: Contract, ts: TermSet) -> None:
    if contract.status != STATUS_PROCESSING:
        contract.status = STATUS_CONFIRMED if ts.all_confirmed else STATUS_WAITING
