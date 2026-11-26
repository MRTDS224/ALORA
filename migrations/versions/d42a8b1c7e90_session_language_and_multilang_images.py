"""session_language_and_multilang_images

Revision ID: d42a8b1c7e90
Revises: c91f3e5a2b40
Create Date: 2026-11-26 11:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d42a8b1c7e90"
down_revision: Union[str, Sequence[str], None] = "c91f3e5a2b40"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("language", sa.String(length=20), nullable=False, server_default="sus"),
    )
    op.create_index("ix_sessions_language", "sessions", ["language"], unique=False)
    # Mark visual elicitation prompts as multilingual ('mul') so they are shared across languages
    op.execute("UPDATE prompts SET language = 'mul' WHERE prompt_type = 'image' AND language = 'sus'")


def downgrade() -> None:
    op.execute("UPDATE prompts SET language = 'sus' WHERE prompt_type = 'image' AND language = 'mul'")
    op.drop_index("ix_sessions_language", table_name="sessions")
    op.drop_column("sessions", "language")
