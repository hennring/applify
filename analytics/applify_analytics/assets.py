"""Python assets of the market analysis (§5.8)."""

from collections.abc import Iterator
from datetime import UTC, datetime

from applify.config import get_settings
from applify.db.session import get_engine
from applify.llm import get_llm
from dagster import (
    AssetExecutionContext,
    AssetKey,
    AssetSpec,
    Config,
    MaterializeResult,
    MetadataValue,
    asset,
    multi_asset,
)
from pydantic import Field
from sqlalchemy import Connection, func, select

from applify_analytics.features import store
from applify_analytics.features.reference import refresh_reference
from applify_analytics.features.regions import refresh_job_regions

JOBS = AssetKey(["app", "jobs"])
JOB_FEATURES = AssetKey(["features", "job_features"])
PROFILES = AssetKey(["app", "profiles"])
REFERENCE = [
    AssetSpec(
        AssetKey(["features", "skill_taxonomy"]),
        group_name="features",
        description="Skills and categories from skills.yaml.",
    ),
    AssetSpec(
        AssetKey(["features", "role_families"]),
        group_name="features",
        description="Role families from roles.yaml.",
    ),
    AssetSpec(
        AssetKey(["features", "profile_role_families"]),
        deps=[PROFILES],
        group_name="features",
        description="Desired roles of each profile, mapped to role families.",
    ),
    AssetSpec(
        AssetKey(["features", "states"]),
        group_name="features",
        description="German states with population, from resources/states.json.",
    ),
]


@multi_asset(specs=REFERENCE)
def reference_tables() -> Iterator[MaterializeResult[None]]:
    """Reference data for dbt, written from the YAML files (single source of truth)."""
    with get_engine().begin() as conn:
        counts = refresh_reference(conn)
    for spec, rows in zip(REFERENCE, counts.values(), strict=True):
        yield MaterializeResult(asset_key=spec.key, metadata={"rows": rows})


@asset(
    key=AssetKey(["features", "job_regions"]),
    deps=[JOBS],
    group_name="features",
    description="Federal state of each job with coordinates (point in the state outlines).",
)
def job_regions() -> MaterializeResult[None]:
    with get_engine().begin() as conn:
        assigned = refresh_job_regions(conn)
    return MaterializeResult(metadata={"jobs_with_state": assigned})


class JobFeaturesConfig(Config):
    # Jobs the LLM looks at per run (≈ 20 s each on the GPU); 0 switches it off (D22).
    llm_budget: int = Field(default=50, ge=0, le=1000)


@asset(
    key=JOB_FEATURES,
    deps=[JOBS],
    group_name="features",
    description="Role family, seniority, experience, salary, skills, languages and degree "
    "per job; rules first (D22).",
)
def job_features(
    context: AssetExecutionContext, config: JobFeaturesConfig
) -> MaterializeResult[None]:
    engine = get_engine()
    with engine.begin() as conn:
        stats = store.refresh(conn)
    context.log.info(f"{stats.extracted} of {stats.jobs} jobs extracted, {stats.removed} removed")
    llm_stats = store.run_llm(
        engine, get_llm(), get_settings().ollama_model, config.llm_budget, context.log.info
    )
    with engine.begin() as conn:
        coverage = _coverage(conn)
        left = store.count_queue(conn)
        store.record_coverage(
            conn,
            context.run_id,
            {
                "recorded_at": datetime.now(UTC),
                "jobs": stats.jobs,
                "full_text": _full_text_jobs(conn),
                "coverage": coverage,
                "llm_processed": llm_stats.processed,
                "llm_failed": llm_stats.failed,
                "llm_queue": left,
            },
        )
    return MaterializeResult(
        metadata={
            "jobs": stats.jobs,
            "extracted": stats.extracted,
            "removed": stats.removed,
            "llm_processed": llm_stats.processed,
            "llm_failed": llm_stats.failed,
            "llm_queue_left": left,
            **{f"coverage_{k}": MetadataValue.float(v) for k, v in coverage.items()},
        }
    )


def _full_text_jobs(conn: Connection) -> int:
    from applify.db.models import Job

    return conn.scalar(select(func.count()).select_from(Job).where(Job.has_full_text)) or 0


def _coverage(conn: Connection) -> dict[str, float]:
    """Share of full-text jobs with each feature determined."""
    from applify.db.models import Job

    t = store.job_features
    full = (
        select(t)
        .join(Job.__table__, Job.__table__.c.id == t.c.job_id)
        .where(Job.__table__.c.has_full_text)
        .subquery()
    )
    total = conn.scalar(select(func.count()).select_from(full)) or 0
    if not total:
        return {}
    columns = {
        "role_family": full.c.role_family.is_not(None),
        "seniority": full.c.seniority.is_not(None),
        "years": full.c.years_min.is_not(None),
        "salary_eur": full.c.salary_min_eur.is_not(None) | full.c.salary_max_eur.is_not(None),
        "skills": func.cardinality(full.c.skills) > 0,
    }
    return {
        name: round(
            (conn.scalar(select(func.count()).select_from(full).where(cond)) or 0) / total, 3
        )
        for name, cond in columns.items()
    }
