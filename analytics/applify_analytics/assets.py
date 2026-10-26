"""Python assets of the market analysis (§5.8)."""

from applify.db.session import get_engine
from dagster import AssetExecutionContext, AssetKey, MaterializeResult, MetadataValue, asset
from sqlalchemy import Connection, func, select

from applify_analytics.features import store

JOBS = AssetKey(["app", "jobs"])
JOB_FEATURES = AssetKey(["features", "job_features"])


@asset(
    key=JOB_FEATURES,
    deps=[JOBS],
    group_name="features",
    description="Role family, seniority, experience, salary, skills, languages and degree "
    "per job; rules first (D22).",
)
def job_features(context: AssetExecutionContext) -> MaterializeResult[None]:
    with get_engine().begin() as conn:
        stats = store.refresh(conn)
        coverage = _coverage(conn)
    context.log.info(f"{stats.extracted} of {stats.jobs} jobs extracted, {stats.removed} removed")
    return MaterializeResult(
        metadata={
            "jobs": stats.jobs,
            "extracted": stats.extracted,
            "removed": stats.removed,
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
