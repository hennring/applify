from dataclasses import replace
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from applify.db.models import JobSighting, JobVersion, SearchRun
from applify.services.search_runner import fail_interrupted_runs
from applify.sources.base import JobPosting, SourceError
from tests.conftest import FakeSource

PROFILE = {
    "roles": ["Fullstack Entwickler"],
    "skills": [{"name": "Python", "weight": "must"}],
    "locations": [{"name": "Leipzig", "radius_km": 30}, {"name": "Dresden", "radius_km": 20}],
}

LEIPZIG_ONLY = {**PROFILE, "locations": [{"name": "Leipzig", "radius_km": 30}]}


def ba(external_id: str, title: str, company: str = "Pixelwerk GmbH") -> JobPosting:
    return JobPosting(
        source="ba",
        external_id=external_id,
        url=f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{external_id}",
        title=title,
        company=company,
        location_raw="04109 Leipzig",
    )


def test_fully_remote_profile_also_searches_all_of_germany(
    api: TestClient, fake_source: FakeSource
) -> None:
    fake_source.remote_search = True  # type: ignore[attr-defined]
    api.put("/api/profile", json=LEIPZIG_ONLY)
    run = api.post("/api/runs").json()
    assert [q.remote for q in fake_source.queries] == [False, False]

    fake_source.queries.clear()
    remote_job = replace(
        ba("9", "Fullstack Entwickler Python (100 % remote)"),
        location_raw="80331 München",
        remote_type="remote",
    )
    fake_source.postings = {"Fullstack Entwickler": [remote_job]}
    api.put(
        "/api/profile",
        json={**LEIPZIG_ONLY, "remote_pref": "remote"},
    )
    run = api.post("/api/runs").json()

    queries = [(q.term, q.location, q.remote) for q in fake_source.queries]
    assert queries == [
        ("Fullstack Entwickler", "Leipzig", False),
        ("Fullstack Python", "Leipzig", False),
        ("Fullstack Entwickler", None, True),
        ("Fullstack Python", None, True),
    ]
    assert api.get(f"/api/runs/{run['id']}").json()["status"] == "done"
    # Far away but fully remote: in the list, not hidden by the radius.
    items = api.get("/api/matches").json()["items"]
    assert [m["job"]["location_raw"] for m in items] == ["80331 München"]


def test_duplicates_within_one_result_are_rated_once(
    api: TestClient, fake_source: FakeSource
) -> None:
    api.put("/api/profile", json=LEIPZIG_ONLY)
    fake_source.postings = {
        "Fullstack Entwickler": [
            ba("1", "Fullstack Entwickler (m/w/d)"),
            ba("2", "Fullstack Entwickler*in"),
        ]
    }
    run = api.post("/api/runs").json()

    run = api.get(f"/api/runs/{run['id']}").json()
    assert run["status"] == "done", run["step"]
    assert (run["stats"]["ba"]["new"], run["stats"]["ba"]["duplicate"]) == (1, 1)
    assert api.get("/api/matches").json()["total"] == 1


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
        "filtered": 0,
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


def test_runs_record_what_they_saw(
    api: TestClient, fake_source: FakeSource, db_session: Session
) -> None:
    """Raw layer (§5.8): one sighting per run and posting, one version per content."""
    api.put("/api/profile", json=LEIPZIG_ONLY)
    fake_source.postings = {"Fullstack Entwickler": [ba("1", "Fullstack Entwickler")]}
    runs = [api.post("/api/runs").json()["id"] for _ in range(3)]

    sightings = db_session.execute(
        select(JobSighting.run_id, JobSighting.content_hash, JobSighting.job_id).order_by(
            JobSighting.id
        )
    ).all()
    assert [s.run_id for s in sightings] == runs
    job_id = sightings[0].job_id
    assert job_id is not None and all(s.job_id == job_id for s in sightings)
    # As delivered: the first run completed the posting, later runs only see the search
    # result again (known postings are not completed twice). Same content, same version.
    versions = db_session.scalars(select(JobVersion).order_by(JobVersion.first_seen_at)).all()
    assert [v.has_full_text for v in versions] == [True, False]
    assert versions[0].description.startswith("Volltext")
    assert [s.content_hash for s in sightings] == [
        versions[0].content_hash,
        versions[1].content_hash,
        versions[1].content_hash,
    ]

    # Changed content: a new version; the old ones stay.
    fake_source.postings["Fullstack Entwickler"][0].title = "Fullstack Entwickler (m/w/d)"
    api.post("/api/runs")
    assert db_session.scalar(select(func.count()).select_from(JobSighting)) == 4
    assert db_session.scalar(select(func.count()).select_from(JobVersion)) == 3
