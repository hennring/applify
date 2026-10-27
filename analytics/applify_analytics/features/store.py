"""Tables of the features schema, owned by the pipeline (not by Alembic, D19)."""

import logging
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from applify.db.models import Job
from applify.llm import LLMError, LLMProvider
from applify.services.skills import SkillTaxonomy, get_taxonomy
from sqlalchemy import (
    ARRAY,
    Boolean,
    Column,
    DateTime,
    Integer,
    MetaData,
    PrimaryKeyConstraint,
    String,
    Table,
    delete,
    func,
    or_,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.engine import Connection, Engine

from applify_analytics.features import llm
from applify_analytics.features.extract import (
    PROMPT_VERSION,
    Features,
    JobInput,
    extract,
    extractor_version,
)

log = logging.getLogger(__name__)

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
    Column("salary_currency", String(5)),
    Column("salary_period", String(5)),
    Column("skills", ARRAY(String), nullable=False, server_default="{}"),
    Column("skill_candidates", ARRAY(String), nullable=False, server_default="{}"),
    Column("languages", JSONB, nullable=False, server_default="{}"),
    Column("degrees", ARRAY(String), nullable=False, server_default="{}"),
    Column("is_agency", Boolean, nullable=False, server_default="false"),
    Column("origin", JSONB, nullable=False, server_default="{}"),
    Column("extracted_at", DateTime(timezone=True), nullable=False),
)

# LLM answers per text and prompt version (D22); a failed call is stored with its error,
# so the job is not tried again until the prompt changes.
llm_cache = Table(
    "llm_cache",
    metadata,
    Column("input_hash", String(64), nullable=False),
    Column("prompt_version", String(40), nullable=False),
    Column("model", String(100), nullable=False),
    Column("result", JSONB),
    Column("error", String(500)),
    Column("created_at", DateTime(timezone=True), nullable=False),
    PrimaryKeyConstraint("input_hash", "prompt_version"),
)

# Coverage of the features per pipeline run (§5.9, tab "Daten"): the share of full-text
# jobs with each feature determined, and the state of the LLM queue.
coverage_history = Table(
    "coverage_history",
    metadata,
    Column("dagster_run_id", String(64), primary_key=True),
    Column("recorded_at", DateTime(timezone=True), nullable=False),
    Column("jobs", Integer, nullable=False),
    Column("full_text", Integer, nullable=False),
    Column("coverage", JSONB, nullable=False),
    Column("llm_processed", Integer, nullable=False),
    Column("llm_failed", Integer, nullable=False),
    Column("llm_queue", Integer, nullable=False),
)

# Latest result of each asset check per pipeline run.
check_results = Table(
    "check_results",
    metadata,
    Column("dagster_run_id", String(64), nullable=False),
    Column("check_name", String(60), nullable=False),
    Column("passed", Boolean, nullable=False),
    Column("detail", JSONB, nullable=False, server_default="{}"),
    Column("checked_at", DateTime(timezone=True), nullable=False),
    PrimaryKeyConstraint("dagster_run_id", "check_name"),
)

# One row per run of the market pipeline, written by the run status sensors; the
# dashboard reads it to tell whether the analysis is current, running or failed.
pipeline_runs = Table(
    "pipeline_runs",
    metadata,
    Column("dagster_run_id", String(64), primary_key=True),
    # Newest finished search run when the pipeline started: what the analysis covers.
    Column("search_run_id", Integer),
    Column("status", String(10), nullable=False),  # running / success / failed / canceled
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("finished_at", DateTime(timezone=True)),
)

# Prefix of LLMError for answers that failed validation (applify.llm.ollama).
INVALID_ANSWER = "invalid structured output"

JOB_COLUMNS = (
    Job.id,
    Job.title,
    Job.description,
    Job.has_full_text,
    Job.salary_min,
    Job.salary_max,
    Job.company,
)


@dataclass(frozen=True)
class RefreshStats:
    jobs: int
    extracted: int
    removed: int


@dataclass(frozen=True)
class LlmStats:
    queued: int
    processed: int
    failed: int


ADDED_COLUMNS = (("job_features", "is_agency", "boolean NOT NULL DEFAULT false"),)


# Key of the advisory lock that serializes the DDL below: pipeline steps run in parallel
# processes and would otherwise race to create the same new table.
DDL_LOCK = 0x617070_6C6966


def ensure_tables(conn: Connection) -> None:
    conn.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": DDL_LOCK})
    conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))
    metadata.create_all(conn)
    # create_all leaves existing tables alone; columns added later are added here.
    for table, column, ddl in ADDED_COLUMNS:
        conn.execute(text(f"ALTER TABLE {SCHEMA}.{table} ADD COLUMN IF NOT EXISTS {column} {ddl}"))


def record_pipeline_run(
    conn: Connection,
    dagster_run_id: str,
    status: str,
    started_at: datetime,
    *,
    search_run_id: int | None = None,
    finished_at: datetime | None = None,
) -> None:
    """Insert or update the status row of a pipeline run; the search run is kept once set."""
    ensure_tables(conn)
    row = {
        "dagster_run_id": dagster_run_id,
        "search_run_id": search_run_id,
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
    }
    stmt = insert(pipeline_runs).values(row)
    conn.execute(
        stmt.on_conflict_do_update(
            index_elements=[pipeline_runs.c.dagster_run_id],
            set_={
                "status": stmt.excluded.status,
                "finished_at": stmt.excluded.finished_at,
                "search_run_id": func.coalesce(
                    pipeline_runs.c.search_run_id, stmt.excluded.search_run_id
                ),
            },
        )
    )


def record_coverage(conn: Connection, dagster_run_id: str, row: dict[str, Any]) -> None:
    ensure_tables(conn)
    stmt = insert(coverage_history).values(dagster_run_id=dagster_run_id, **row)
    conn.execute(
        stmt.on_conflict_do_update(
            index_elements=[coverage_history.c.dagster_run_id],
            set_={k: stmt.excluded[k] for k in row},
        )
    )


def record_check(
    conn: Connection, dagster_run_id: str, name: str, passed: bool, detail: dict[str, Any]
) -> None:
    ensure_tables(conn)
    row = {"passed": passed, "detail": detail, "checked_at": datetime.now(UTC)}
    stmt = insert(check_results).values(dagster_run_id=dagster_run_id, check_name=name, **row)
    conn.execute(
        stmt.on_conflict_do_update(
            index_elements=[check_results.c.dagster_run_id, check_results.c.check_name],
            set_={k: stmt.excluded[k] for k in row},
        )
    )


def _job_input(row: Any) -> JobInput:
    return JobInput(
        row.id,
        row.title,
        row.description,
        row.has_full_text,
        row.salary_min,
        row.salary_max,
        row.company,
    )


def _features(job: JobInput, taxonomy: SkillTaxonomy, cached: dict[str, Any] | None) -> Features:
    """Rules, then the cached LLM answer for this text, if any."""
    features = extract(job, taxonomy)
    if cached is not None:
        llm.apply(features, llm.LlmJobFeatures.model_validate(cached), taxonomy)
    return features


def _cached_results(conn: Connection) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        select(llm_cache.c.input_hash, llm_cache.c.result).where(
            llm_cache.c.prompt_version == PROMPT_VERSION, llm_cache.c.result.is_not(None)
        )
    )
    return {row.input_hash: row.result for row in rows}


def _upsert(conn: Connection, rows: list[dict[str, Any]]) -> None:
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


def _row(job: JobInput, version: str, features: Features, now: datetime) -> dict[str, Any]:
    return {
        "job_id": job.job_id,
        "input_hash": job.input_hash(),
        "extractor_version": version,
        **asdict(features),
        "extracted_at": now,
    }


def refresh(conn: Connection, now: datetime | None = None) -> RefreshStats:
    """Extract features for new and changed jobs; drop rows of jobs that are gone.

    A job is extracted again when its text changed or the extractor version differs.
    Cached LLM answers are applied again without calling the LLM.
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
    jobs = [_job_input(row) for row in conn.execute(select(*JOB_COLUMNS))]
    taxonomy = get_taxonomy()
    cached = _cached_results(conn)
    rows = [
        _row(job, version, _features(job, taxonomy, cached.get(digest)), now)
        for job in jobs
        if current.get(job.job_id) != ((digest := job.input_hash()), version)
    ]
    _upsert(conn, rows)
    gone = set(current) - {job.job_id for job in jobs}
    if gone:
        conn.execute(delete(job_features).where(job_features.c.job_id.in_(gone)))
    return RefreshStats(jobs=len(jobs), extracted=len(rows), removed=len(gone))


def llm_queue(conn: Connection, limit: int) -> list[JobInput]:
    """Full-text jobs without an LLM answer: gaps in role or seniority first, then newest."""
    asked = select(llm_cache.c.input_hash).where(llm_cache.c.prompt_version == PROMPT_VERSION)
    gaps = or_(job_features.c.role_family.is_(None), job_features.c.seniority.is_(None))
    rows = conn.execute(
        select(*JOB_COLUMNS)
        .join(job_features, job_features.c.job_id == Job.id)
        .where(Job.has_full_text, job_features.c.input_hash.not_in(asked))
        .order_by(gaps.desc(), Job.first_seen_at.desc(), Job.id.desc())
        .limit(limit)
    )
    return [_job_input(row) for row in rows]


def count_queue(conn: Connection) -> int:
    asked = select(llm_cache.c.input_hash).where(llm_cache.c.prompt_version == PROMPT_VERSION)
    return (
        conn.scalar(
            select(func.count())
            .select_from(Job)
            .join(job_features, job_features.c.job_id == Job.id)
            .where(Job.has_full_text, job_features.c.input_hash.not_in(asked))
        )
        or 0
    )


def run_llm(
    engine: Engine,
    provider: LLMProvider,
    model: str,
    budget: int,
    progress: Callable[[str], None] = log.info,
) -> LlmStats:
    """Ask the LLM for up to `budget` queued jobs; each answer is committed right away."""
    with engine.connect() as conn:
        queue = llm_queue(conn, budget)
        queued = count_queue(conn)
    taxonomy = get_taxonomy()
    version = extractor_version()
    system = llm.system_prompt()
    processed = failed = 0
    for n, job in enumerate(queue, 1):
        digest = job.input_hash()
        result: dict[str, Any] | None = None
        error: str | None = None
        try:
            answer = provider.generate_structured(
                llm.prompt_for(job.title, job.description), llm.LlmJobFeatures, system=system
            )
            result = answer.model_dump()
        except LLMError as exc:
            if not str(exc).startswith(INVALID_ANSWER):
                # Ollama unreachable or failing: stop without caching, try again next run.
                progress(f"LLM nicht erreichbar, Abbruch: {exc}")
                break
            error = str(exc)[:500]
        now = datetime.now(UTC)
        with engine.begin() as conn:
            conn.execute(
                insert(llm_cache)
                .values(
                    input_hash=digest,
                    prompt_version=PROMPT_VERSION,
                    model=model,
                    result=result,
                    error=error,
                    created_at=now,
                )
                .on_conflict_do_nothing()
            )
            if result is not None:
                _upsert(conn, [_row(job, version, _features(job, taxonomy, result), now)])
        if error is None:
            processed += 1
        else:
            failed += 1
        progress(f"LLM {n}/{len(queue)}: {job.title[:60]}" + (f" – {error}" if error else ""))
    return LlmStats(queued=queued, processed=processed, failed=failed)
