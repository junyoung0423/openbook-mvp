"""process_contract 결과(조항·조건)를 DB에 저장한다 (정준영).

POST /contracts 처리 작업(박다연 담당)은 파싱 → process_contract → save_process_result 순서로
부르면 된다. 같은 계약서를 다시 처리하면 조항과 조건을 새 결과로 바꾼다 (확정도 지워진다).

계약서 상태
- 조항이 있으면 '조건 확인 대기' (조건 추출이 실패해도 사용자가 직접 입력할 수 있으므로)
- 조항이 없으면 '처리중'으로 둔다. 화면은 result.clause_review_needed로 안내한다.
result의 warnings·error·clause_review_needed는 contracts 테이블에 자리가 없다. 저장할지는
박다연 님과 정한다 (GET /contracts/{id}가 보여 줘야 함).
"""

from __future__ import annotations

from sqlalchemy import delete
from sqlalchemy.orm import Session

from openbook.db import ClauseRecord, Contract, TermRecord, term_to_record
from openbook.pipeline import ProcessResult
from openbook.schemas import Term, TermKey, TermStatus

STATUS_WAITING = "조건 확인 대기"


def save_process_result(db: Session, contract: Contract, result: ProcessResult) -> None:
    """조항과 조건을 바꿔 넣는다. 커밋은 부르는 쪽이 한다."""
    if result.contract_id != contract.id:
        raise ValueError("처리 결과의 contract_id가 계약서와 다릅니다.")
    db.execute(delete(ClauseRecord).where(ClauseRecord.contract_id == contract.id))
    db.execute(delete(TermRecord).where(TermRecord.contract_id == contract.id))
    db.add_all(
        ClauseRecord(
            contract_id=contract.id,
            id=c.id,
            no=c.no,
            title=c.title,
            text=c.text,
            type_id=c.type_id,
            std_clause_id=c.std_clause_id,
        )
        for c in result.clauses
    )
    # 조건은 항상 9개를 둔다. 추출이 실패했거나(terms=None) 빠진 key는 '찾지 못함'으로 넣어야
    # 사용자가 직접 입력해 확정할 수 있다 (TermSet.all_confirmed는 9개 key가 모두 있어야 true).
    terms = {t.key: t for t in (result.terms.terms if result.terms else [])}
    db.add_all(
        term_to_record(contract.id, terms.get(k) or Term(key=k, status=TermStatus.NOT_FOUND))
        for k in TermKey
    )
    if result.clauses:
        contract.status = STATUS_WAITING
