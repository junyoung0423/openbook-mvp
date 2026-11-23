"""정산서 저장과 대조 (명세서 5절 P0).

- 정산서는 같은 계약서에 기간별로 여러 번 넣을 수 있다.
- 대조는 필수 조건 5개가 모두 확정된 계약서에서만 연다 (409 TERMS_NOT_CONFIRMED).
- 대조는 조회할 때마다 다시 계산하고 reconciliations 테이블의 결과를 바꿔 넣는다.
"""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Response
from sqlalchemy import delete, select

from openbook.api.deps import DB, OwnedContract, api_error
from openbook.api.routes.terms import _records, _term_set
from openbook.db import Reconciliation
from openbook.db import Statement as StatementRow
from openbook.engine import StatementInput
from openbook.reconcile import StatementLine, StatementWithLines, reconcile
from openbook.schemas import Statement, StatementDeduction
from openbook.schemas.reconciliation import ReconciliationReport

router = APIRouter(tags=["statements"])


class StatementOut(Statement):
    id: str

    @classmethod
    def of(cls, row: StatementRow) -> StatementOut:
        return cls(
            id=row.id,
            period_start=row.period_start,
            period_end=row.period_end,
            gross=row.gross,
            net_revenue=row.net_revenue,
            deductions=[StatementDeduction.model_validate(d) for d in row.deductions],
            reported_settlement=row.reported_settlement,
            reported_withholding=row.reported_withholding,
            reported_payout=row.reported_payout,
        )


def _dec(x: Decimal | None) -> Decimal | None:
    return None if x is None else Decimal(x)


def _rows(db: DB, contract_id: str) -> list[StatementRow]:
    return list(
        db.scalars(
            select(StatementRow)
            .where(StatementRow.contract_id == contract_id)
            .order_by(StatementRow.period_start, StatementRow.period_end, StatementRow.id)
        ).all()
    )


@router.post("/contracts/{contract_id}/statements", response_model=StatementOut, status_code=201)
def create_statement(body: Statement, contract: OwnedContract, db: DB) -> StatementOut:
    row = StatementRow(
        contract_id=contract.id,
        period_start=body.period_start,
        period_end=body.period_end,
        gross=body.gross,
        net_revenue=body.net_revenue,
        deductions=[d.model_dump(mode="json") for d in body.deductions],
        reported_settlement=body.reported_settlement,
        reported_withholding=body.reported_withholding,
        reported_payout=body.reported_payout,
    )
    db.add(row)
    db.commit()
    return StatementOut.of(row)


@router.get("/contracts/{contract_id}/statements", response_model=list[StatementOut])
def list_statements(contract: OwnedContract, db: DB) -> list[StatementOut]:
    return [StatementOut.of(r) for r in _rows(db, contract.id)]


@router.delete("/contracts/{contract_id}/statements/{statement_id}", status_code=204)
def delete_statement(statement_id: str, contract: OwnedContract, db: DB) -> Response:
    row = db.get(StatementRow, statement_id)
    if row is None or row.contract_id != contract.id:
        raise api_error(404, "STATEMENT_NOT_FOUND", "정산서를 찾을 수 없습니다.")
    db.delete(row)
    db.commit()
    return Response(status_code=204)


@router.get("/contracts/{contract_id}/reconciliations", response_model=ReconciliationReport)
def get_reconciliations(contract: OwnedContract, db: DB) -> ReconciliationReport:
    ts = _term_set(contract.id, _records(db, contract.id))
    if not ts.all_confirmed:
        raise api_error(
            409, "TERMS_NOT_CONFIRMED", "필수 조건을 모두 확정한 뒤 대조할 수 있습니다."
        )
    rows = _rows(db, contract.id)
    inputs = [
        StatementWithLines(
            statement=StatementInput(
                id=r.id,
                period_start=r.period_start,
                period_end=r.period_end,
                gross=Decimal(r.gross),
                reported_payout=Decimal(r.reported_payout),
                net_revenue=_dec(r.net_revenue),
                reported_settlement=_dec(r.reported_settlement),
                reported_withholding=_dec(r.reported_withholding),
            ),
            lines=tuple(StatementLine(d["name"], Decimal(d["amount"])) for d in r.deductions),
        )
        for r in rows
    ]
    report = reconcile(contract.id, ts.terms, inputs)

    ids = [r.id for r in rows]
    if ids:
        db.execute(delete(Reconciliation).where(Reconciliation.statement_id.in_(ids)))
    db.add_all(
        Reconciliation(
            statement_id=item.statement_id,
            computed_payout=item.computed_payout,
            diff=item.diff,
            breakdown=[s.model_dump(mode="json") for s in item.breakdown],
            unsupported_reason=item.unsupported_reason,
        )
        for item in report.items
    )
    db.commit()
    return report
