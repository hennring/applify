"""jobs: towns named in the location

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-31 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from applify.services.geo import get_gazetteer

# revision identifiers, used by Alembic.
revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column("cities", postgresql.ARRAY(sa.String()), server_default="{}", nullable=False),
    )
    # Backfill from the offline geo data, like new postings get it.
    connection = op.get_bind()
    gazetteer = get_gazetteer()
    rows = connection.execute(sa.text("SELECT id, location_raw FROM jobs")).all()
    values = [
        {"id": id_, "cities": cities}
        for id_, location_raw in rows
        if (cities := gazetteer.cities(location_raw))
    ]
    if values:
        connection.execute(sa.text("UPDATE jobs SET cities = :cities WHERE id = :id"), values)


def downgrade() -> None:
    op.drop_column("jobs", "cities")
