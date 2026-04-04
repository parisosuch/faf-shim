"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-04-03

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Import models so SQLModel.metadata is fully populated
    import app.db.models  # noqa: F401
    from sqlmodel import SQLModel

    bind = op.get_bind()
    # checkfirst=True makes this safe for existing deployments —
    # tables that already exist are skipped.
    SQLModel.metadata.create_all(bind, checkfirst=True)


def downgrade() -> None:
    import app.db.models  # noqa: F401
    from sqlmodel import SQLModel

    bind = op.get_bind()
    SQLModel.metadata.drop_all(bind)
