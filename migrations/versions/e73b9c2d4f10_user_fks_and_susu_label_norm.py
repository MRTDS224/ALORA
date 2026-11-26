"""Add collector_user_id on sessions, reviewer_user_id on quality_annotations, normalize native_language to Soussou.

Revision ID: e73b9c2d4f10
Revises: d42a8b1c7e90
Create Date: 2026-11-26 12:55:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e73b9c2d4f10"
down_revision: Union[str, None] = "d42a8b1c7e90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column(
            "collector_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_sessions_collector_user_id", "sessions", ["collector_user_id"], unique=False)

    op.add_column(
        "quality_annotations",
        sa.Column(
            "reviewer_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_quality_annotations_reviewer_user_id",
        "quality_annotations",
        ["reviewer_user_id"],
        unique=False,
    )

    op.execute(
        "UPDATE speakers SET native_language = 'Soussou' "
        "WHERE LOWER(COALESCE(native_language, '')) IN ('susu', 'soussou')"
    )


def downgrade() -> None:
    op.drop_index("ix_quality_annotations_reviewer_user_id", table_name="quality_annotations")
    op.drop_column("quality_annotations", "reviewer_user_id")
    op.drop_index("ix_sessions_collector_user_id", table_name="sessions")
    op.drop_column("sessions", "collector_user_id")
