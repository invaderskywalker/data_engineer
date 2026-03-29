"""Add test tables TestTableOne and TestTableTwo

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-29
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "test_table_one",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )

    op.create_table(
        "test_table_two",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("description", sa.String(256), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("test_table_two")
    op.drop_table("test_table_one")
    