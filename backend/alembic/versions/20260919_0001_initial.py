"""initial schema: users + events

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-19

Схема строго соответствует каноническому контракту AGENTS.md:
events: id (UUID, клиентский), user_id (FK -> users, CASCADE), title,
event_type (lecture|practice|lab|exam|other), start_time/end_time
(TIMESTAMPTZ, end_time > start_time), location/teacher/description/
recurrence_rule (nullable), updated_at (TIMESTAMPTZ, UTC),
is_deleted (soft delete). Индексы: (user_id, updated_at),
(user_id, start_time).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "subscription_tier",
            sa.String(length=32),
            server_default="free",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("event_type", sa.String(length=20), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("teacher", sa.String(length=255), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("recurrence_rule", sa.String(length=255), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.CheckConstraint(
            "end_time > start_time", name="ck_events_end_after_start"
        ),
        sa.CheckConstraint(
            "event_type IN ('lecture', 'practice', 'lab', 'exam', 'other')",
            name="ck_events_event_type",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_events_user_updated", "events", ["user_id", "updated_at"]
    )
    op.create_index(
        "idx_events_user_start_time", "events", ["user_id", "start_time"]
    )


def downgrade() -> None:
    op.drop_index("idx_events_user_start_time", table_name="events")
    op.drop_index("idx_events_user_updated", table_name="events")
    op.drop_table("events")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
