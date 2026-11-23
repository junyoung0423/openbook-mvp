"""정산서 지급내역형 칸: 회사입금액, 정산액, 원천징수 (계산 규칙 R1–R12)

Revision ID: 0003_statement_columns
Revises: 0002_auth
"""

import sqlalchemy as sa

from alembic import op

revision = "0003_statement_columns"
down_revision = "0002_auth"
branch_labels = None
depends_on = None

MONEY = sa.Numeric(38, 0)


def upgrade() -> None:
    with op.batch_alter_table("statements") as batch:
        batch.add_column(sa.Column("net_revenue", MONEY, nullable=True))
        batch.add_column(sa.Column("reported_settlement", MONEY, nullable=True))
        batch.add_column(sa.Column("reported_withholding", MONEY, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("statements") as batch:
        batch.drop_column("reported_withholding")
        batch.drop_column("reported_settlement")
        batch.drop_column("net_revenue")
