"""raw layer: job sightings and versions

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-26 15:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Existing postings get one version each with a placeholder hash; the first real run
# stores their content as delivered under the real hash.
BACKFILL_VERSIONS = """
INSERT INTO raw.job_versions (
    content_hash, source, external_id, job_id, title, company, location_raw, remote_type,
    salary_min, salary_max, description, has_full_text, posted_at, payload, first_seen_at
)
SELECT
    encode(sha256(convert_to('backfill:' || s.source || ':' || s.external_id, 'UTF8')), 'hex'),
    s.source, s.external_id, j.id, j.title, j.company, j.location_raw, j.remote_type,
    j.salary_min, j.salary_max, j.description, j.has_full_text, j.posted_at, s.raw,
    j.first_seen_at
FROM job_sources s JOIN jobs j ON j.id = s.job_id
"""

# History starts with what the app knows: first seen, and last fetched if later.
BACKFILL_SIGHTINGS = """
INSERT INTO raw.job_sightings (run_id, seen_at, source, external_id, job_id, content_hash)
SELECT NULL, seen.at, s.source, s.external_id, s.job_id,
    encode(sha256(convert_to('backfill:' || s.source || ':' || s.external_id, 'UTF8')), 'hex')
FROM job_sources s
JOIN jobs j ON j.id = s.job_id
CROSS JOIN LATERAL (
    SELECT j.first_seen_at AS at
    UNION
    SELECT s.fetched_at WHERE s.fetched_at > j.first_seen_at
) seen
"""


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE SCHEMA IF NOT EXISTS raw")
    op.create_table(
        "job_sightings",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=True),
        sa.Column(
            "seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("external_id", sa.String(length=200), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema="raw",
    )
    op.create_index(
        "ix_job_sightings_source_external_id",
        "job_sightings",
        ["source", "external_id"],
        schema="raw",
    )
    op.create_index("ix_raw_job_sightings_run_id", "job_sightings", ["run_id"], schema="raw")
    op.create_index("ix_raw_job_sightings_seen_at", "job_sightings", ["seen_at"], schema="raw")
    op.create_index("ix_raw_job_sightings_job_id", "job_sightings", ["job_id"], schema="raw")
    op.create_table(
        "job_versions",
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("external_id", sa.String(length=200), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("company", sa.Text(), nullable=False),
        sa.Column("location_raw", sa.Text(), server_default="", nullable=False),
        sa.Column("remote_type", sa.String(length=10), nullable=True),
        sa.Column("salary_min", sa.Integer(), nullable=True),
        sa.Column("salary_max", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("has_full_text", sa.Boolean(), nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "payload", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("content_hash"),
        schema="raw",
    )
    op.create_index(
        "ix_job_versions_source_external_id",
        "job_versions",
        ["source", "external_id"],
        schema="raw",
    )
    op.execute(BACKFILL_VERSIONS)
    op.execute(BACKFILL_SIGHTINGS)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("job_versions", schema="raw")
    op.drop_table("job_sightings", schema="raw")
    op.execute("DROP SCHEMA IF EXISTS raw")
