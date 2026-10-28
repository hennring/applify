"""jobs: town population

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-28 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from applify.services.geo import get_gazetteer

# revision identifiers, used by Alembic.
revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("population", sa.Integer(), nullable=True))
    # Backfill from the offline geo data, like new postings get it.
    connection = op.get_bind()
    gazetteer = get_gazetteer()
    rows = connection.execute(sa.text("SELECT id, location_raw, lat, lon FROM jobs")).all()
    values = [
        {"id": id_, "population": population}
        for id_, location_raw, lat, lon in rows
        if (population := gazetteer.population(location_raw, lat, lon)) is not None
    ]
    if values:
        connection.execute(
            sa.text("UPDATE jobs SET population = :population WHERE id = :id"), values
        )


def downgrade() -> None:
    op.drop_column("jobs", "population")
