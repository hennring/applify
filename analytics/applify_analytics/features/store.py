"""Table features.job_features, owned by the pipeline (not by Alembic, D19)."""

from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from applify.db.models import Job
from applify.services.skills import get_taxonomy
from sqlalchemy import (
    ARRAY,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    delete,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.engine import Connection

from applify_analytics.features.extract import Features, JobInput, extract, extractor_version

SCHEMA = "features"
metadata = MetaData(schema=SCHEMA)

job_features = Table(
    "job_features",
    metadata,
    Column("job_id", Integer, primary_key=True),
    Column("input_hash", String(64), nullable=False),
    Column("extractor_version", String(40), nullable=False),
    Column("role_family", String(30)),
    Column("seniority", String(10)),
    Column("years_min", Integer),
    Column("years_max", Integer),
    Column("salary_min_eur", Integer),
    Column("salary_max_eur", Integer),
    Column("salary_currency", String(3)),
    Column("salary_period", String(5)),
    Column("skills", ARRAY(String), nullable=False, server_default="{}"),
    Column("skill_candidates", ARRAY(String), nullable=False, server_default="{}"),
    Column("languages", JSONB, nullable=False, server_default="{}"),
    Column("degrees", ARRAY(String), nullable=False, server_default="{}"),
    Column("origin", JSONB, nullable=False, server_default="{}"),
    Column("extracted_at", DateTime(timezone=True), nullable=False),
)


@dataclass(frozen=True)
class RefreshStats:
    jobs: int
    extracted: int
    removed: int


def ensure_tables(conn: Connection) -> None:
    conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))
    metadata.create_all(conn)


def refresh(conn: Connection, now: datetime | None = None) -> RefreshStats:
    """Extract features for new and changed jobs; drop rows of jobs that are gone.

    A job is extracted again when its text changed or the extractor version differs.
    """
    now = now or datetime.now(UTC)
    ensure_tables(conn)
    version = extractor_version()
    current = {
        row.job_id: (row.input_hash, row.extractor_version)
        for row in conn.execute(
            select(
                job_features.c.job_id, job_features.c.input_hash, job_features.c.extractor_version
            )
        )
    }
    jobs = [
        JobInput(r.id, r.title, r.description, r.has_full_text, r.salary_min, r.salary_max)
        for r in conn.execute(
            select(
                Job.id,
                Job.title,
                Job.description,
                Job.has_full_text,
                Job.salary_min,
                Job.salary_max,
            )
        )
    ]
    taxonomy = get_taxonomy()
    rows = []
    for job in jobs:
        digest = job.input_hash()
        if current.get(job.job_id) == (digest, version):
            continue
        rows.append(_row(job.job_id, digest, version, extract(job, taxonomy), now))
    for start in range(0, len(rows), 500):
        statement = insert(job_features).values(rows[start : start + 500])
        conn.execute(
            statement.on_conflict_do_update(
                index_elements=[job_features.c.job_id],
                set_={
                    c.name: statement.excluded[c.name] for c in job_features.c if c.name != "job_id"
                },
            )
        )
    gone = set(current) - {job.job_id for job in jobs}
    if gone:
        conn.execute(delete(job_features).where(job_features.c.job_id.in_(gone)))
    return RefreshStats(jobs=len(jobs), extracted=len(rows), removed=len(gone))


def _row(
    job_id: int, digest: str, version: str, features: Features, now: datetime
) -> dict[str, object]:
    return {
        "job_id": job_id,
        "input_hash": digest,
        "extractor_version": version,
        **asdict(features),
        "skill_candidates": [],
        "extracted_at": now,
    }
