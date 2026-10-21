"""timestamps with time zone

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-21 14:52:11.204331

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Column → time zone of the values stored so far: DB defaults ran in UTC (container),
# values set in Python used the local time of the dev machine.
COLUMNS = {
    ("users", "created_at"): "UTC",
    ("documents", "uploaded_at"): "UTC",
    ("documents", "extracted_at"): "Europe/Berlin",
    ("profiles", "updated_at"): "UTC",
    ("jobs", "posted_at"): "UTC",
    ("jobs", "first_seen_at"): "Europe/Berlin",
    ("jobs", "updated_at"): "UTC",
    ("job_sources", "fetched_at"): "Europe/Berlin",
    ("search_runs", "started_at"): "UTC",
    ("search_runs", "finished_at"): "Europe/Berlin",
}


def upgrade() -> None:
    """Upgrade schema."""
    for (table, column), zone in COLUMNS.items():
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {column} TYPE timestamptz "
            f"USING {column} AT TIME ZONE '{zone}'"
        )


def downgrade() -> None:
    """Downgrade schema."""
    for table, column in COLUMNS:
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {column} TYPE timestamp "
            f"USING {column} AT TIME ZONE 'UTC'"
        )
