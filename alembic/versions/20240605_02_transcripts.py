"""add transcripts table"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20240605_02_transcripts"
down_revision = "20240605_01_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "transcripts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("job_id", sa.String(length=64), nullable=False, unique=True),
        sa.Column("audio_key", sa.String(length=512), nullable=False),
        sa.Column("transcript_key", sa.String(length=512), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("language", sa.String(length=32), nullable=True),
        sa.Column("quality_profile", sa.String(length=32), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("tags", sa.String(length=255), nullable=True),
        sa.Column("segments", sa.Text(), nullable=True),
        sa.Column("duration_seconds", sa.Numeric(scale=2), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_transcripts_user_id", "transcripts", ["user_id"])
    op.create_index("ix_transcripts_profile_id", "transcripts", ["profile_id"])
    op.create_index("ix_transcripts_job_id", "transcripts", ["job_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_transcripts_job_id", table_name="transcripts")
    op.drop_index("ix_transcripts_profile_id", table_name="transcripts")
    op.drop_index("ix_transcripts_user_id", table_name="transcripts")
    op.drop_table("transcripts")
