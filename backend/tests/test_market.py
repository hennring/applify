import shutil
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from applify.db.models import Job, SearchRun
from applify.services import market
from applify.services.skills import SKILLS_FILE, get_taxonomy


def test_dashboard_waits_for_the_pipeline(api: TestClient) -> None:
    # The test database has no marts: the analytics pipeline never ran there.
    data = api.get("/api/market").json()
    assert data["available"] is False
    assert data["analysis"]["state"] == "unknown"


NOW = datetime(2026, 10, 26, 18, 0, tzinfo=UTC)


def search_run(session: Session, minutes: int, status: str = "done") -> int:
    run = SearchRun(user_id=1, status=status, stats={}, errors=[])
    run.finished_at = NOW + timedelta(minutes=minutes)
    session.add(run)
    session.flush()
    return run.id


def pipeline_run(session: Session, minutes: int, status: str, search_run_id: int) -> None:
    # The table belongs to the analytics pipeline; the test database lacks it.
    session.execute(
        text("""create schema if not exists features;
            create table if not exists features.pipeline_runs (
                dagster_run_id varchar(64) primary key, search_run_id int,
                status varchar(10) not null, started_at timestamptz not null,
                finished_at timestamptz)""")
    )
    session.execute(
        text("insert into features.pipeline_runs values (:id, :search, :status, :start, :end)"),
        {
            "id": f"run-{minutes}",
            "search": search_run_id,
            "status": status,
            "start": NOW + timedelta(minutes=minutes),
            "end": None if status == "running" else NOW + timedelta(minutes=minutes + 2),
        },
    )


def test_analysis_covering_the_newest_search_run_is_current(db_session: Session) -> None:
    first = search_run(db_session, 0)
    pipeline_run(db_session, 1, "success", first)
    status = market.analysis_status(db_session)
    assert status["state"] == "current"
    assert status["analyzed_at"] == NOW + timedelta(minutes=3)
    assert status["search_run_at"] == NOW


def test_newer_search_run_leaves_the_analysis_pending(db_session: Session) -> None:
    pipeline_run(db_session, 1, "success", search_run(db_session, 0))
    search_run(db_session, 10)
    search_run(db_session, 20, status="running")  # not finished: nothing to analyse yet
    status = market.analysis_status(db_session)
    assert status["state"] == "pending"
    assert status["latest_search_run_at"] == NOW + timedelta(minutes=10)


def test_running_and_failed_pipeline_runs(db_session: Session) -> None:
    first = search_run(db_session, 0)
    pipeline_run(db_session, 1, "success", first)
    pipeline_run(db_session, 5, "failed", first)
    status = market.analysis_status(db_session)
    # The last successful run still dates the marts.
    assert (status["state"], status["analyzed_at"]) == ("failed", NOW + timedelta(minutes=3))
    pipeline_run(db_session, 9, "running", first)
    assert market.analysis_status(db_session)["state"] == "running"


@pytest.fixture
def skills_file(tmp_path: Path) -> Iterator[Path]:
    copy = tmp_path / "skills.yaml"
    shutil.copy(SKILLS_FILE, copy)
    yield copy
    get_taxonomy.cache_clear()


def job(description: str) -> Job:
    return Job(
        title="Data Engineer",
        company="Acme",
        description=description,
        company_norm="acme",
        title_norm="data engineer",
        fingerprint="x" * 40,
        skills=["Python"],
    )


def test_accepted_candidate_joins_the_taxonomy(db_session: Session, skills_file: Path) -> None:
    named, other = job("Wir nutzen Snowflake und Python."), job("Nur Python.")
    db_session.add_all([named, other])
    db_session.flush()

    touched = market.accept_candidate(db_session, " Snowflake ", "data", skills_file=skills_file)

    assert touched == 1
    content = skills_file.read_text(encoding="utf-8")
    assert "# --- Added from the market analysis ---\n" in content
    assert content.endswith('\n- {name: "Snowflake", category: data}\n')
    # Rescanned with the next rating; the other job keeps its skills.
    db_session.refresh(named)
    db_session.refresh(other)
    assert named.skills is None
    assert other.skills == ["Python"]


@pytest.mark.parametrize(
    ("name", "category", "message"),
    [
        ("Python", "language", "schon in der Taxonomie"),
        ("Snowflake", "warehouse", "Unbekannte Kategorie"),
        ("<script>", "data", "Ungültiger Name"),
    ],
)
def test_invalid_candidates_are_refused(
    db_session: Session, skills_file: Path, name: str, category: str, message: str
) -> None:
    before = skills_file.read_text(encoding="utf-8")
    with pytest.raises(market.CandidateError, match=message):
        market.accept_candidate(db_session, name, category, skills_file=skills_file)
    assert skills_file.read_text(encoding="utf-8") == before


def test_agency_filter_is_optional() -> None:
    where, _ = market.selection_where(market.MarketFilter(), user_id=1)
    assert "is_agency" not in where
    where, _ = market.selection_where(market.MarketFilter(agencies=False), user_id=1)
    assert "not f.is_agency" in where


def test_data_tab_is_empty_without_marts(api: TestClient) -> None:
    assert api.get("/api/market/data").json() == {
        "sources": [],
        "history": [],
        "checks": [],
        "runs": [],
    }


def test_top_roles_of_an_employer() -> None:
    assert market.most_common(["Backend", "Data", "Backend", "Frontend", "Data", "Backend"]) == [
        "Backend",
        "Data",
        "Frontend",
    ]
    assert market.most_common(None) == []
