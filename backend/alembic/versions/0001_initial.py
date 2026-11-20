"""initial database schema

Revision ID: 0001_initial
Revises:
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

JSON_DOCUMENT = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
MONEY = sa.Numeric(38, 0)
SCALAR_NUMERIC = sa.Numeric(38, 18)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "contracts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("file_ref", sa.String(1024)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_contracts_user_id", "contracts", ["user_id"])

    op.create_table(
        "clauses",
        sa.Column("contract_id", sa.String(36), sa.ForeignKey("contracts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("no", sa.String(64)),
        sa.Column("title", sa.String(255)),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("type_id", sa.String(128)),
        sa.Column("std_clause_id", sa.String(128)),
    )

    op.create_table(
        "terms",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("contract_id", sa.String(36), sa.ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("value", JSON_DOCUMENT),
        sa.Column("numeric_value", SCALAR_NUMERIC),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("source_clause_id", sa.String(64)),
        sa.Column("quote", sa.Text()),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("contract_id", "key", name="uq_terms_contract_key"),
    )
    op.create_index("ix_terms_contract_id", "terms", ["contract_id"])

    op.create_table(
        "statements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("contract_id", sa.String(36), sa.ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("gross", MONEY, nullable=False),
        sa.Column("deductions", JSON_DOCUMENT, nullable=False),
        sa.Column("reported_payout", MONEY, nullable=False),
    )
    op.create_index("ix_statements_contract_id", "statements", ["contract_id"])

    op.create_table(
        "reconciliations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("statement_id", sa.String(36), sa.ForeignKey("statements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("computed_payout", MONEY),
        sa.Column("diff", MONEY),
        sa.Column("breakdown", JSON_DOCUMENT, nullable=False),
        sa.Column("unsupported_reason", sa.Text()),
    )
    op.create_index("ix_reconciliations_statement_id", "reconciliations", ["statement_id"])

    op.create_table(
        "qa_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("contract_id", sa.String(36), sa.ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("cited_clause_ids", JSON_DOCUMENT, nullable=False),
    )
    op.create_index("ix_qa_logs_contract_id", "qa_logs", ["contract_id"])

    op.create_table(
        "alerts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("contract_id", sa.String(36), sa.ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_alerts_contract_id", "alerts", ["contract_id"])


def downgrade() -> None:
    op.drop_table("alerts")
    op.drop_table("qa_logs")
    op.drop_table("reconciliations")
    op.drop_table("statements")
    op.drop_table("terms")
    op.drop_table("clauses")
    op.drop_table("contracts")
    op.drop_table("users")
