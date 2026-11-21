"""waxal_collection_fields

Revision ID: 9c4f2a8b1d30
Revises: defe874d90ca
Create Date: 2026-11-21 08:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9c4f2a8b1d30"
down_revision: Union[str, Sequence[str], None] = "defe874d90ca"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add WAXAL-aligned fields for oral consent, image elicitation, session task, and acoustic QA."""
    op.add_column(
        "speakers",
        sa.Column("consent_audio_object_key", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "sessions",
        sa.Column(
            "target_task",
            sa.String(length=20),
            nullable=False,
            server_default="asr",
        ),
    )
    op.add_column(
        "prompts",
        sa.Column("media_object_key", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "prompts",
        sa.Column("media_content_type", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "prompts",
        sa.Column("min_duration_seconds", sa.Float(), nullable=True),
    )
    op.add_column(
        "recordings",
        sa.Column("snr_db", sa.Float(), nullable=True),
    )
    op.add_column(
        "recordings",
        sa.Column("peak_amplitude", sa.Float(), nullable=True),
    )
    op.add_column(
        "recordings",
        sa.Column(
            "clipping_detected",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "recordings",
        sa.Column("speech_ratio", sa.Float(), nullable=True),
    )
    op.add_column(
        "recordings",
        sa.Column("auto_quality_flags", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    """Revert WAXAL-aligned fields."""
    op.drop_column("recordings", "auto_quality_flags")
    op.drop_column("recordings", "speech_ratio")
    op.drop_column("recordings", "clipping_detected")
    op.drop_column("recordings", "peak_amplitude")
    op.drop_column("recordings", "snr_db")
    op.drop_column("prompts", "min_duration_seconds")
    op.drop_column("prompts", "media_content_type")
    op.drop_column("prompts", "media_object_key")
    op.drop_column("sessions", "target_task")
    op.drop_column("speakers", "consent_audio_object_key")
