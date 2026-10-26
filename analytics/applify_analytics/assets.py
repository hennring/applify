"""Python assets of the market analysis (§5.8)."""

from applify.config import get_settings
from applify.db.session import get_engine
from applify.llm import get_llm
from dagster import (
    AssetExecutionContext,
    AssetKey,
    Config,
    MaterializeResult,
    MetadataValue,
    asset,
)
from pydantic import Field
from sqlalchemy import Connection, func, select

from applify_analytics.features import store

JOBS = AssetKey(["app", "jobs"])
JOB_FEATURES = AssetKey(["features", "job_features"])


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
    with engine.connect() as conn:
        coverage = _coverage(conn)
        left = store.count_queue(conn)
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
