"""audit_logs and transcription_reviews (multi-reviewer peer validation)

Revision ID: c91f3e5a2b40
Revises: 7b2d9e4a1f60
Create Date: 2026-11-26 10:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c91f3e5a2b40"
down_revision: Union[str, Sequence[str], None] = "7b2d9e4a1f60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("transcriptions", sa.Column("author_user_id", sa.UUID(), nullable=True))
    op.add_column("transcriptions", sa.Column("notes", sa.Text(), nullable=True))
    op.create_index("ix_transcriptions_author_user_id", "transcriptions", ["author_user_id"], unique=False)
    op.create_foreign_key(
        "fk_transcriptions_author_user_id_users",
        "transcriptions",
        "users",
        ["author_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "transcription_reviews",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("transcription_id", sa.UUID(), nullable=False),
        sa.Column("reviewer_user_id", sa.UUID(), nullable=False),
        sa.Column("reviewer_name", sa.String(length=150), nullable=True),
        sa.Column("decision", sa.String(length=30), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["transcription_id"], ["transcriptions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("transcription_id", "reviewer_user_id", name="uq_transcription_reviewer"),
    )
    op.create_index("ix_transcription_reviews_transcription_id", "transcription_reviews", ["transcription_id"], unique=False)
    op.create_index("ix_transcription_reviews_reviewer_user_id", "transcription_reviews", ["reviewer_user_id"], unique=False)

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("actor_user_id", sa.UUID(), nullable=True),
        sa.Column("actor_email", sa.String(length=255), nullable=True),
        sa.Column("actor_role", sa.String(length=30), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("target_type", sa.String(length=50), nullable=True),
        sa.Column("target_id", sa.String(length=100), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"], unique=False)
    op.create_index("ix_audit_logs_actor_email", "audit_logs", ["actor_email"], unique=False)
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"], unique=False)
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_email", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_user_id", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_transcription_reviews_reviewer_user_id", table_name="transcription_reviews")
    op.drop_index("ix_transcription_reviews_transcription_id", table_name="transcription_reviews")
    op.drop_table("transcription_reviews")

    op.drop_constraint("fk_transcriptions_author_user_id_users", "transcriptions", type_="foreignkey")
    op.drop_index("ix_transcriptions_author_user_id", table_name="transcriptions")
    op.drop_column("transcriptions", "notes")
    op.drop_column("transcriptions", "author_user_id")
