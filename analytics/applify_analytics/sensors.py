"""Start the pipeline after every finished search run (D20)."""

from collections.abc import Iterator

from applify.db.models import SearchRun
from applify.db.session import get_engine
from dagster import (
    DefaultSensorStatus,
    RunRequest,
    SensorEvaluationContext,
    SkipReason,
    define_asset_job,
    sensor,
)
from sqlalchemy import select

market_pipeline = define_asset_job(
    "market_pipeline",
    description="Reference tables → job features (rules, LLM) → dbt build with tests.",
)


@sensor(
    job=market_pipeline,
    minimum_interval_seconds=60,
    default_status=DefaultSensorStatus.RUNNING,
    description="Runs the market pipeline once for each search run that finished.",
)
def search_run_finished(context: SensorEvaluationContext) -> Iterator[RunRequest | SkipReason]:
    last = int(context.cursor) if context.cursor else None
    with get_engine().connect() as conn:
        if last is None:
            # First start: begin with the runs from now on, the backlog needs one manual run.
            newest = conn.scalar(select(SearchRun.id).order_by(SearchRun.id.desc()).limit(1))
            context.update_cursor(str(newest or 0))
            yield SkipReason("Sensor started; waiting for the next finished search run.")
            return
        finished = conn.scalars(
            select(SearchRun.id)
            .where(SearchRun.id > last, SearchRun.status != "running")
            .order_by(SearchRun.id)
        ).all()
    if not finished:
        yield SkipReason("No new finished search run.")
        return
    # One pipeline run covers all runs finished since the last check.
    newest = finished[-1]
    context.update_cursor(str(newest))
    yield RunRequest(run_key=f"search-run-{newest}", tags={"search_run": str(newest)})
