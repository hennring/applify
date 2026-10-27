"""Dagster code location of the market analysis (§5.8, D20)."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from dagster import AssetExecutionContext, Definitions
from dagster_dbt import DbtCliResource, DbtProject, dbt_assets

from applify_analytics.assets import job_features, job_regions, reference_tables, skill_stacks
from applify_analytics.checks import feature_coverage, llm_failures
from applify_analytics.sensors import market_pipeline, search_run_finished, status_sensors

DBT_DIR = Path(__file__).resolve().parent.parent / "dbt"

dbt_project = DbtProject(project_dir=DBT_DIR, profiles_dir=DBT_DIR)
# In `dagster dev` the manifest is (re)built on load; deployments build it ahead of time.
dbt_project.prepare_if_dev()


@dbt_assets(manifest=dbt_project.manifest_path)
def market_dbt_assets(context: AssetExecutionContext, dbt: DbtCliResource) -> Iterator[Any]:
    """All dbt models and their tests: staging → intermediate → marts."""
    yield from dbt.cli(["build"], context=context).stream()


defs = Definitions(
    assets=[reference_tables, job_features, job_regions, skill_stacks, market_dbt_assets],
    asset_checks=[feature_coverage, llm_failures],
    jobs=[market_pipeline],
    sensors=[search_run_finished, *status_sensors],
    resources={"dbt": DbtCliResource(project_dir=dbt_project)},
)
