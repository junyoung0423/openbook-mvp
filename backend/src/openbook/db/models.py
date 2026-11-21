"""오픈북 MVP 데이터 모델.

금액은 NUMERIC으로 저장하며 Python에서는 Decimal로 다룬다.
terms.value와 계산 breakdown처럼 구조가 항목마다 다른 값은 JSON/JSONB로 저장한다.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from openbook.db.base import JSON_DOCUMENT, Base

MONEY = Numeric(38, 0, asdecimal=True)
SCALAR_NUMERIC = Numeric(38, 18, asdecimal=True)


def _id() -> str:
    return str(uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    contracts: Mapped[list[Contract]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )


class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    file_ref: Mapped[str | None] = mapped_column(String(1024))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="처리중")
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    user: Mapped[User] = relationship(back_populates="contracts")
    clauses: Mapped[list[ClauseRecord]] = relationship(
        back_populates="contract", cascade="all, delete-orphan", passive_deletes=True
    )
    terms: Mapped[list[TermRecord]] = relationship(
        back_populates="contract", cascade="all, delete-orphan", passive_deletes=True
    )
    statements: Mapped[list[Statement]] = relationship(
        back_populates="contract", cascade="all, delete-orphan", passive_deletes=True
    )
    qa_logs: Mapped[list[QaLog]] = relationship(
        back_populates="contract", cascade="all, delete-orphan", passive_deletes=True
    )
    alerts: Mapped[list[Alert]] = relationship(
        back_populates="contract", cascade="all, delete-orphan", passive_deletes=True
    )


class ClauseRecord(Base):
    __tablename__ = "clauses"

    contract_id: Mapped[str] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"), primary_key=True
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    no: Mapped[str | None] = mapped_column(String(64))
    title: Mapped[str | None] = mapped_column(String(255))
    text: Mapped[str] = mapped_column(Text, nullable=False)
    type_id: Mapped[str | None] = mapped_column(String(128))
    std_clause_id: Mapped[str | None] = mapped_column(String(128))

    contract: Mapped[Contract] = relationship(back_populates="clauses")


class TermRecord(Base):
    __tablename__ = "terms"
    __table_args__ = (UniqueConstraint("contract_id", "key", name="uq_terms_contract_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    contract_id: Mapped[str] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[object | None] = mapped_column(JSON_DOCUMENT, nullable=True)
    # mg_amount와 scalar rs_rate의 정밀 숫자 미러. JSON 값은 API 형식(문자열)을 보존한다.
    numeric_value: Mapped[Decimal | None] = mapped_column(SCALAR_NUMERIC, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    source_clause_id: Mapped[str | None] = mapped_column(String(64))
    quote: Mapped[str | None] = mapped_column(Text)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    contract: Mapped[Contract] = relationship(back_populates="terms")


class Statement(Base):
    __tablename__ = "statements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    contract_id: Mapped[str] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    gross: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    deductions: Mapped[list[dict]] = mapped_column(JSON_DOCUMENT, nullable=False, default=list)
    reported_payout: Mapped[Decimal] = mapped_column(MONEY, nullable=False)

    contract: Mapped[Contract] = relationship(back_populates="statements")
    reconciliations: Mapped[list[Reconciliation]] = relationship(
        back_populates="statement", cascade="all, delete-orphan", passive_deletes=True
    )


class Reconciliation(Base):
    __tablename__ = "reconciliations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    statement_id: Mapped[str] = mapped_column(
        ForeignKey("statements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    computed_payout: Mapped[Decimal | None] = mapped_column(MONEY)
    diff: Mapped[Decimal | None] = mapped_column(MONEY)
    breakdown: Mapped[list[dict]] = mapped_column(JSON_DOCUMENT, nullable=False, default=list)
    unsupported_reason: Mapped[str | None] = mapped_column(Text)

    statement: Mapped[Statement] = relationship(back_populates="reconciliations")


class QaLog(Base):
    __tablename__ = "qa_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    contract_id: Mapped[str] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    cited_clause_ids: Mapped[list[str]] = mapped_column(JSON_DOCUMENT, nullable=False, default=list)

    contract: Mapped[Contract] = relationship(back_populates="qa_logs")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    contract_id: Mapped[str] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    contract: Mapped[Contract] = relationship(back_populates="alerts")
