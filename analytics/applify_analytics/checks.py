"""Data quality checks beyond the dbt tests (§5.8); dbt tests become checks by themselves."""

from applify.db.session import get_engine
from dagster import (
    AssetCheckExecutionContext,
    AssetCheckResult,
    AssetCheckSeverity,
    MetadataValue,
    asset_check,
)
from sqlalchemy import func, select

from applify_analytics.assets import JOB_FEATURES, _coverage
from applify_analytics.features import store
from applify_analytics.features.extract import PROMPT_VERSION

# Acceptance of M5: role family and seniority known for ≥ 80 % of full-text jobs.
MIN_COVERAGE = 0.8
MAX_LLM_FAILURES = 0.1


@asset_check(asset=JOB_FEATURES, description="Role family and seniority known for ≥ 80 %.")
def feature_coverage(context: AssetCheckExecutionContext) -> AssetCheckResult:
    with get_engine().begin() as conn:
        coverage = _coverage(conn)
        short = {
            k: v for k in ("role_family", "seniority") if (v := coverage.get(k, 0)) < MIN_COVERAGE
        }
        detail = {"threshold": MIN_COVERAGE, "below": short}
        store.record_check(conn, context.run.run_id, "feature_coverage", not short, detail)
    return AssetCheckResult(
        passed=not short,
        severity=AssetCheckSeverity.WARN,
        description=None if not short else f"below {MIN_COVERAGE:.0%}: {short}",
        metadata={k: MetadataValue.float(v) for k, v in coverage.items()},
    )


@asset_check(asset=JOB_FEATURES, description="Share of failed LLM answers stays below 10 %.")
def llm_failures(context: AssetCheckExecutionContext) -> AssetCheckResult:
    cache = store.llm_cache
    with get_engine().begin() as conn:
        store.ensure_tables(conn)
        total = (
            conn.scalar(select(func.count()).where(cache.c.prompt_version == PROMPT_VERSION)) or 0
        )
        failed = (
            conn.scalar(
                select(func.count()).where(
                    cache.c.prompt_version == PROMPT_VERSION, cache.c.error.is_not(None)
                )
            )
            or 0
        )
        share = failed / total if total else 0.0
        detail = {"threshold": MAX_LLM_FAILURES, "failed_share": share, "answers": total}
        passed = share <= MAX_LLM_FAILURES
        store.record_check(conn, context.run.run_id, "llm_failures", passed, detail)
    return AssetCheckResult(
        passed=passed,
        severity=AssetCheckSeverity.WARN,
        metadata={"answers": total, "failed": failed, "failed_share": MetadataValue.float(share)},
    )
