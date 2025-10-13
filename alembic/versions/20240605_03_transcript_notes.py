"""Add notes column to transcripts

Revision ID: 20240605_03_transcript_notes
Revises: 20240605_02_transcripts
Create Date: 2024-06-05 00:00:00
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20240605_03_transcript_notes"
down_revision = "20240605_02_transcripts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("transcripts", sa.Column("notes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("transcripts", "notes")
