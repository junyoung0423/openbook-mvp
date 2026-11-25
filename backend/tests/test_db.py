from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select

from openbook.db import Base, Contract, Statement, User, create_db_engine, make_session_factory
from openbook.db.models import TermRecord
from openbook.db.term_storage import record_to_term, term_to_record
from openbook.schemas import Term, TermKey, TermStatus


def _db(tmp_path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    return engine, make_session_factory(engine)


def test_money_round_trip_uses_decimal(tmp_path):
    engine, sessions = _db(tmp_path)
    with sessions.begin() as session:
        user = User(email="dayeon@example.test")
        contract = Contract(user=user, title="가상 계약")
        statement = Statement(
            contract=contract,
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 31),
            gross=Decimal(123456789),
            deductions=[{"name": "결제 수수료", "rate": "0.1", "amount": None}],
            reported_payout=Decimal(98765432),
        )
        session.add(statement)
        session.flush()
        statement_id = statement.id

    with sessions() as session:
        saved = session.get(Statement, statement_id)
        assert isinstance(saved.gross, Decimal)
        assert saved.gross == Decimal(123456789)
        assert saved.reported_payout == Decimal(98765432)
    engine.dispose()


def test_term_money_and_rate_round_trip_without_float(tmp_path):
    engine, sessions = _db(tmp_path)
    now = datetime.now(UTC)
    with sessions.begin() as session:
        user = User(email="term@example.test")
        contract = Contract(user=user, title="가상 계약")
        session.add(contract)
        session.flush()

        mg = Term(
            key=TermKey.MG_AMOUNT,
            value="5000000",
            status=TermStatus.USER_INPUT,
            confirmed=True,
            confirmed_at=now,
        )
        rate = Term(
            key=TermKey.RS_RATE,
            value="0.6",
            status=TermStatus.USER_INPUT,
            confirmed=True,
            confirmed_at=now,
        )
        mg_row = term_to_record(contract.id, mg)
        rate_row = term_to_record(contract.id, rate)
        session.add_all([mg_row, rate_row])
        session.flush()
        mg_id, rate_id = mg_row.id, rate_row.id

    with sessions() as session:
        mg_saved = session.get(TermRecord, mg_id)
        rate_saved = session.get(TermRecord, rate_id)
        assert mg_saved.value == "5000000"
        assert rate_saved.value == "0.6"
        assert mg_saved.numeric_value == Decimal(5000000)
        # SQLite NUMERIC은 내부 변환으로 소수 정밀도가 달라질 수 있다.
        assert isinstance(rate_saved.numeric_value, Decimal)
        assert record_to_term(mg_saved).value == Decimal(5000000)
        assert record_to_term(rate_saved).value == Decimal("0.6")
    engine.dispose()


def test_contract_delete_cascades_children(tmp_path):
    engine, sessions = _db(tmp_path)
    with sessions.begin() as session:
        user = User(email="delete@example.test")
        contract = Contract(user=user, title="삭제 테스트")
        statement = Statement(
            contract=contract,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            gross=Decimal(1000),
            deductions=[],
            reported_payout=Decimal(600),
        )
        session.add(statement)
        session.flush()
        contract_id = contract.id

    with sessions.begin() as session:
        contract = session.get(Contract, contract_id)
        session.delete(contract)

    with sessions() as session:
        assert session.scalar(select(Statement).where(Statement.contract_id == contract_id)) is None
    engine.dispose()


def test_normalize_url_turns_vercel_postgres_into_psycopg():
    from openbook.db.session import normalize_url

    assert normalize_url("postgres://u:p@h/db?sslmode=require") == (
        "postgresql+psycopg://u:p@h/db?sslmode=require"
    )
    assert normalize_url("postgresql://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert normalize_url("postgresql+psycopg://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert normalize_url("sqlite:///./openbook.db") == "sqlite:///./openbook.db"
