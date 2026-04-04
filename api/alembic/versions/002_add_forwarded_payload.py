"""Add forwarded_payload to webhook_log

Revision ID: 002
Revises: 001
Create Date: 2026-04-03

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = [c["name"] for c in inspect(bind).get_columns("webhook_log")]
    if "forwarded_payload" not in cols:
        with op.batch_alter_table("webhook_log") as batch_op:
            batch_op.add_column(sa.Column("forwarded_payload", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("webhook_log") as batch_op:
        batch_op.drop_column("forwarded_payload")
