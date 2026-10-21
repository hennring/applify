from dataclasses import replace
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from applify.db.models import SearchRun
from applify.services.search_runner import fail_interrupted_runs
from applify.sources.base import JobPosting, SourceError
from tests.conftest import FakeSource

PROFILE = {
    "roles": ["Fullstack Entwickler"],
    "skills": [{"name": "Python", "weight": "must"}],
    "locations": [{"name": "Leipzig", "radius_km": 30}, {"name": "Dresden", "radius_km": 20}],
}


def ba(external_id: str, title: str, company: str = "Pixelwerk GmbH") -> JobPosting:
    return JobPosting(
        source="ba",
        external_id=external_id,
        url=f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{external_id}",
        title=title,
        company=company,
        location_raw="04109 Leipzig",
    )


def test_run_stores_jobs_without_duplicates(api: TestClient, fake_source: FakeSource) -> None:
    api.put("/api/profile", json=PROFILE)
    fake_source.postings = {
        "Fullstack Entwickler": [ba("1", "Fullstack Entwickler (m/w/d)"), ba("2", "Data Engineer")],
        # The same listing again, and the same job under another reference number.
        "Fullstack Python": [
            ba("1", "Fullstack Entwickler (m/w/d)"),
            ba("3", "Fullstack Entwickler*in"),
        ],
    }

    # The runner is synchronous in tests, so the run has finished.
    run = api.post("/api/runs").json()
    run = api.get(f"/api/runs/{run['id']}").json()
    assert run["status"] == "done"
    assert run["progress"] == 1
    assert run["stats"]["ba"] == {
        "label": "Bundesagentur für Arbeit",
        "found": 3,
        "new": 2,
        "duplicate": 1,
        "known": 0,
        "errors": 0,
    }
    # Terms × locations, with radius.
    assert [(q.term, q.location, q.radius_km) for q in fake_source.queries] == [
        ("Fullstack Entwickler", "Leipzig", 30),
        ("Fullstack Python", "Leipzig", 30),
        ("Fullstack Entwickler", "Dresden", 20),
        ("Fullstack Python", "Dresden", 20),
    ]
    assert fake_source.completed == ["1", "2", "3"]

    jobs = api.get("/api/jobs").json()
    assert jobs["total"] == 2
    fullstack = next(j for j in jobs["items"] if j["title"] == "Fullstack Entwickler")
    assert len(fullstack["sources"]) == 2
    assert fullstack["has_full_text"]

    detail = api.get(f"/api/jobs/{fullstack['id']}").json()
    assert detail["description"].startswith("Volltext")
    assert api.get("/api/runs/latest").json()["id"] == run["id"]

    # A second run finds the same listings: nothing new, no details fetched again.
    fake_source.completed.clear()
    second = api.post("/api/runs").json()
    stats = api.get(f"/api/runs/{second['id']}").json()["stats"]["ba"]
    assert (stats["new"], stats["known"]) == (0, 3)
    assert fake_source.completed == []
    assert api.get("/api/jobs").json()["total"] == 2


def test_source_errors_are_recorded_and_the_run_continues(
    api: TestClient, fake_source: FakeSource
) -> None:
    api.put("/api/profile", json=PROFILE | {"locations": [{"name": "Leipzig", "radius_km": 30}]})
    fake_source.errors = {"Fullstack Entwickler": SourceError("rest.arbeitsagentur.de: HTTP 503")}
    fake_source.postings = {"Fullstack Python": [ba("1", "Python Developer")]}

    run_id = api.post("/api/runs").json()["id"]
    run = api.get(f"/api/runs/{run_id}").json()
    assert run["status"] == "done"
    assert run["stats"]["ba"]["errors"] == 1
    assert run["stats"]["ba"]["new"] == 1
    assert run["errors"] == [
        {
            "source": "Bundesagentur für Arbeit",
            "query": "„Fullstack Entwickler“, Leipzig (+30 km)",
            "message": "rest.arbeitsagentur.de: HTTP 503",
        }
    ]


def test_run_without_search_terms_fails(api: TestClient) -> None:
    run_id = api.post("/api/runs").json()["id"]
    run = api.get(f"/api/runs/{run_id}").json()
    assert run["status"] == "failed"
    assert run["step"] == "Keine Wunschrollen oder Pflicht-Skills im Profil"


def test_only_one_run_at_a_time(api: TestClient, db_session: Session) -> None:
    db_session.add(SearchRun(user_id=1, status="running", stats={}, errors=[]))
    db_session.flush()
    response = api.post("/api/runs")
    assert response.status_code == 409

    fail_interrupted_runs(db_session)
    assert api.get("/api/runs/latest").json()["status"] == "failed"


def test_no_run_yet(api: TestClient) -> None:
    assert api.get("/api/runs/latest").json() is None
    assert api.get("/api/runs/999").status_code == 404
    assert api.get("/api/jobs/999").status_code == 404


def test_profile_locations_get_coordinates(api: TestClient, db_session: Session) -> None:
    from applify.db.models import ProfileLocation

    api.put("/api/profile", json=PROFILE)
    leipzig = db_session.query(ProfileLocation).filter_by(name="Leipzig").one()
    assert leipzig.lat is not None and abs(leipzig.lat - 51.34) < 0.1


def test_jobs_are_sorted_by_publication_date(api: TestClient, fake_source: FakeSource) -> None:
    api.put("/api/profile", json=PROFILE | {"locations": [{"name": "Leipzig", "radius_km": 30}]})
    dated = [
        ("1", "Backend Entwickler", datetime(2026, 10, 1, tzinfo=UTC)),
        ("2", "Frontend Entwickler", datetime(2026, 10, 15, tzinfo=UTC)),
        ("3", "Data Engineer", None),
    ]
    fake_source.postings = {
        "Fullstack Entwickler": [
            replace(ba(external_id, title), posted_at=posted)
            for external_id, title, posted in dated
        ]
    }
    api.post("/api/runs")
    titles = [j["title"] for j in api.get("/api/jobs").json()["items"]]
    # Unknown dates last.
    assert titles == ["Frontend Entwickler", "Backend Entwickler", "Data Engineer"]
