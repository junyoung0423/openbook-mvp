import os
from datetime import date
from decimal import Decimal

import pytest

from openbook.db import Base, Contract, Statement, User, create_db_engine, make_session_factory
from openbook.db.models import TermRecord
from openbook.db.term_storage import term_to_record
from openbook.schemas import Term, TermKey, TermStatus

URL = os.getenv("OPENBOOK_TEST_DATABASE_URL", "")
RUN = os.getenv("RUN_POSTGRES_INTEGRATION") == "1" and URL.startswith("postgresql")
pytestmark = pytest.mark.skipif(not RUN, reason="PostgreSQL 통합 테스트 환경이 설정되지 않음")


@pytest.mark.integration
def test_postgres_numeric_round_trip():
    engine = create_db_engine(URL)
    Base.metadata.create_all(engine)
    sessions = make_session_factory(engine)
    email = "numeric-roundtrip@example.test"
    try:
        with sessions.begin() as session:
            user = User(email=email)
            contract = Contract(user=user, title="NUMERIC 왕복")
            row = Statement(
                contract=contract,
                period_start=date(2026, 1, 1),
                period_end=date(2026, 1, 31),
                gross=Decimal(900719925474099312345),
                deductions=[],
                reported_payout=Decimal(900719925474099312344),
            )
            session.add(row)
            session.flush()
            rate = Term(
                key=TermKey.RS_RATE,
                value="0.6",
                status=TermStatus.USER_INPUT,
                confirmed=False,
            )
            rate_row = term_to_record(contract.id, rate)
            session.add(rate_row)
            session.flush()
            row_id, rate_id = row.id, rate_row.id
        with sessions() as session:
            saved = session.get(Statement, row_id)
            saved_rate = session.get(TermRecord, rate_id)
            assert saved.gross == Decimal(900719925474099312345)
            assert saved.reported_payout == Decimal(900719925474099312344)
            assert saved_rate.numeric_value == Decimal("0.6")
    finally:
        with sessions.begin() as session:
            user = session.query(User).filter_by(email=email).one_or_none()
            if user is not None:
                session.delete(user)
        engine.dispose()
