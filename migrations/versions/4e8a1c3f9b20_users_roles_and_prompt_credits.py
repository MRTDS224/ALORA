"""users_roles_and_prompt_credits

Revision ID: 4e8a1c3f9b20
Revises: 9c4f2a8b1d30
Create Date: 2026-11-21 09:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4e8a1c3f9b20"
down_revision: Union[str, Sequence[str], None] = "9c4f2a8b1d30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create users table and add session source + prompt media credit columns."""
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=30), nullable=False, server_default="collector"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.add_column(
        "sessions",
        sa.Column("source", sa.String(length=30), nullable=False, server_default="field_agent"),
    )
    op.add_column(
        "prompts",
        sa.Column("media_license", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "prompts",
        sa.Column("media_attribution", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "prompts",
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_prompts_created_by_user",
        "prompts",
        "users",
        ["created_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Drop users table and added columns."""
    op.drop_constraint("fk_prompts_created_by_user", "prompts", type_="foreignkey")
    op.drop_column("prompts", "created_by_user_id")
    op.drop_column("prompts", "media_attribution")
    op.drop_column("prompts", "media_license")
    op.drop_column("sessions", "source")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
