"""Initial schema for user, profile, and usage meter tables."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20240605_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.sql.expression.true(),
        ),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_profiles_user_id", "profiles", ["user_id"])

    op.create_table(
        "usage_meters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("month", sa.String(length=7), nullable=False),
        sa.Column(
            "transcription_seconds",
            sa.Numeric(scale=2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "transcription_cost",
            sa.Numeric(scale=4),
            nullable=False,
            server_default="0",
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_usage_meters_user_id", "usage_meters", ["user_id"])
    op.create_index("ix_usage_meters_profile_id", "usage_meters", ["profile_id"])
    op.create_index("ix_usage_meters_month", "usage_meters", ["month"])


def downgrade() -> None:
    op.drop_index("ix_usage_meters_month", table_name="usage_meters")
    op.drop_index("ix_usage_meters_profile_id", table_name="usage_meters")
    op.drop_index("ix_usage_meters_user_id", table_name="usage_meters")
    op.drop_table("usage_meters")

    op.drop_index("ix_profiles_user_id", table_name="profiles")
    op.drop_table("profiles")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
