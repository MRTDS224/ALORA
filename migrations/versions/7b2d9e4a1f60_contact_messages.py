"""contact_messages

Revision ID: 7b2d9e4a1f60
Revises: 4e8a1c3f9b20
Create Date: 2026-11-21 10:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7b2d9e4a1f60"
down_revision: Union[str, Sequence[str], None] = "4e8a1c3f9b20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "contact_messages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("sender_name", sa.String(length=150), nullable=False),
        sa.Column("sender_contact", sa.String(length=255), nullable=False),
        sa.Column("profile_type", sa.String(length=60), nullable=False, server_default="autre"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("contact_messages")
