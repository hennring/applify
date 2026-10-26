"""Start the pipeline after every finished search run (D20) and record its status."""

from collections.abc import Iterator
from datetime import UTC, datetime

from applify.db.models import SearchRun
from applify.db.session import get_engine
from dagster import (
    DagsterRunStatus,
    DefaultSensorStatus,
    RunRequest,
    RunStatusSensorContext,
    RunStatusSensorDefinition,
    SensorEvaluationContext,
    SkipReason,
    define_asset_job,
    run_status_sensor,
    sensor,
)
from sqlalchemy import Connection, select

from applify_analytics.features import store

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


# Pipeline status for the dashboard: Dagster reports run events to these sensors.
RECORDED = {
    DagsterRunStatus.STARTED: "running",
    DagsterRunStatus.SUCCESS: "success",
    DagsterRunStatus.FAILURE: "failed",
    DagsterRunStatus.CANCELED: "canceled",
}


def _record_status(run_status: DagsterRunStatus, status: str) -> RunStatusSensorDefinition:
    @run_status_sensor(
        run_status=run_status,
        name=f"pipeline_{status}",
        monitored_jobs=[market_pipeline],
        minimum_interval_seconds=10,
        default_status=DefaultSensorStatus.RUNNING,
        description=f"Marks a market pipeline run as {status} for the dashboard.",
    )
    def record(context: RunStatusSensorContext) -> None:
        run = context.dagster_run
        record = context.instance.get_run_record_by_id(run.run_id)
        now = datetime.now(UTC)
        started = _at(record.start_time if record else None) or now
        finished = None if status == "running" else _at(record.end_time if record else None) or now
        with get_engine().begin() as conn:
            store.record_pipeline_run(
                conn,
                run.run_id,
                status,
                started,
                search_run_id=_covered_search_run(conn, run.tags.get("search_run")),
                finished_at=finished,
            )

    return record


def _at(timestamp: float | None) -> datetime | None:
    return datetime.fromtimestamp(timestamp, UTC) if timestamp else None


def _covered_search_run(conn: Connection, tag: str | None) -> int | None:
    """The search run named by the sensor, else the newest finished one (manual runs)."""
    if tag and tag.isdigit():
        return int(tag)
    return conn.scalar(
        select(SearchRun.id)
        .where(SearchRun.status != "running")
        .order_by(SearchRun.id.desc())
        .limit(1)
    )


status_sensors = [_record_status(run_status, status) for run_status, status in RECORDED.items()]
