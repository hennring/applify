"""Search run stages 2 and 3 (feeds, companies) and the settings, companies, coverage API."""

import time
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from applify.db.models import Company, Job, JobSighting, UserCompany
from applify.services import search_runner
from applify.sources.base import JobPosting, RunSources
from tests.conftest import FIXTURES, FakeSource, FakeWeb

PROFILE = {
    "roles": ["Fullstack Entwickler"],
    "skills": [{"name": "Python", "weight": "must"}],
    "locations": [{"name": "Karlsruhe", "radius_km": 30}],
}
FULL_TEXT = "Wir entwickeln mit Python und Vue. " * 10


def ba(external_id: str, title: str, company: str, description: str = "") -> JobPosting:
    return JobPosting(
        source="ba",
        external_id=external_id,
        url=f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{external_id}",
        title=title,
        company=company,
        location_raw="76131 Karlsruhe",
        description=description,
    )


class FakeFeed:
    name = "arbeitnow"
    label = "Arbeitnow"

    def __init__(self, postings: list[JobPosting]) -> None:
        self.postings = postings

    def fetch(self) -> list[JobPosting]:
        return self.postings

    def complete(self, posting: JobPosting) -> JobPosting:
        return posting


def feed_posting(external_id: str, location: str) -> JobPosting:
    return JobPosting(
        source="arbeitnow",
        external_id=external_id,
        url=f"https://www.arbeitnow.com/view/{external_id}",
        title="Python Developer",
        company="Somewhere GmbH",
        location_raw=location,
        description=FULL_TEXT,
        has_full_text=True,
    )


def run(api: TestClient) -> dict[str, Any]:
    started = api.post("/api/runs").json()
    result: dict[str, Any] = api.get(f"/api/runs/{started['id']}").json()
    assert result["status"] == "done", result["step"]
    return result


def test_feed_postings_are_prefiltered(api: TestClient, run_sources: RunSources) -> None:
    api.put("/api/profile", json=PROFILE)
    run_sources.feeds = [
        FakeFeed(
            [
                feed_posting("a", "Karlsruhe"),
                feed_posting("b", "Hamburg"),
                feed_posting("c", "Paris"),
            ]
        )
    ]

    stats = run(api)["stats"]["arbeitnow"]

    assert (stats["found"], stats["new"], stats["filtered"]) == (3, 1, 2)


def test_companies_from_hits_are_detected_and_their_feeds_read(
    api: TestClient,
    run_sources: RunSources,
    fake_source: FakeSource,
    web: FakeWeb,
    db_session: Session,
) -> None:
    api.put("/api/profile", json=PROFILE)
    fake_source.postings = {
        "Fullstack Entwickler": [
            ba(
                "1",
                "Fullstack Entwickler",
                "Chrono24 GmbH",
                "Bewerbung: https://chrono24.jobs.personio.de/job/1",
            ),
            ba("2", "Backend Entwickler", "Nirgendwo AG"),
        ]
    }
    web.add(
        "https://chrono24.jobs.personio.de/xml",
        (FIXTURES / "ats" / "personio.xml").read_bytes(),
        headers={"ETag": '"v1"'},
    )
    run_sources.client = web.client()

    result = run(api)

    chrono = db_session.scalar(select(Company).where(Company.name_norm == "chrono24"))
    assert chrono is not None
    assert (chrono.ats_type, chrono.ats_token, chrono.detection_status) == (
        "personio",
        "chrono24",
        "done",
    )
    assert chrono.last_checked_at is not None and chrono.last_error is None
    # Karlsruhe, remote with Karlsruhe as another office, and remote only; the profile
    # does not want full remote, so the prefilter drops the last one.
    stats = result["stats"]["ats:personio"]
    assert (stats["label"], stats["found"], stats["new"], stats["filtered"]) == (
        "Personio",
        3,
        2,
        1,
    )
    job = db_session.scalar(select(Job).where(Job.title == "AI Solution Engineer"))
    assert job is not None and job.company_id == chrono.id and job.has_full_text
    nowhere = db_session.scalar(select(Company).where(Company.name_norm == "nirgendwo"))
    assert nowhere is not None and nowhere.ats_type == "unknown"

    # Second run: the unchanged feed answers 304 to the stored ETag.
    seen: list[str | None] = []

    def unchanged(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("If-None-Match"))
        return httpx.Response(304)

    web.pages["https://chrono24.jobs.personio.de/xml"] = unchanged
    again = run(api)
    assert seen == ['"v1"']
    assert again["stats"]["ats:personio"]["found"] == 0
    # Not delivered again, but still listed: seen in the second run with the same content.
    sightings = db_session.execute(
        select(JobSighting.run_id, JobSighting.content_hash)
        .where(JobSighting.source == "ats:personio")
        .order_by(JobSighting.id)
    ).all()
    assert [run_id for run_id, _ in sightings] == [result["id"]] * 2 + [again["id"]] * 2
    assert {h for _, h in sightings[:2]} == {h for _, h in sightings[2:]}


def test_ignored_companies_are_not_read(
    api: TestClient, run_sources: RunSources, web: FakeWeb, db_session: Session
) -> None:
    api.put("/api/profile", json=PROFILE)
    company = Company(
        name="Chrono24",
        name_norm="chrono24",
        discovered_from="user",
        ats_type="personio",
        ats_token="chrono24",
        detection_status="done",
        hints={},
    )
    db_session.add(company)
    db_session.flush()
    db_session.add(UserCompany(user_id=1, company_id=company.id, status="ignore"))
    db_session.flush()
    run_sources.client = web.client()

    run(api)

    assert not any("personio" in url for url in web.urls())


def watch(db_session: Session, company: Company) -> Company:
    db_session.add(company)
    db_session.flush()
    db_session.add(UserCompany(user_id=1, company_id=company.id))
    db_session.flush()
    return company


def test_budget_leaves_undetected_companies_marked(
    api: TestClient,
    run_sources: RunSources,
    web: FakeWeb,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api.put("/api/profile", json=PROFILE)
    company = watch(
        db_session,
        Company(
            name="Langsam GmbH",
            name_norm="langsam",
            website="https://langsam.de",
            discovered_from="user",
            detection_status="pending",
            hints={},
        ),
    )
    run_sources.client = web.client()
    monkeypatch.setattr(search_runner, "COMPANY_BUDGET", 0)

    run(api)

    db_session.refresh(company)
    assert (company.ats_type, company.detection_status) == ("unknown", "done")
    assert company.last_error == search_runner.BUDGET_MESSAGE
    assert not any("langsam.de" in url for url in web.urls())


def test_budget_postpones_workday_details_to_the_next_run(
    api: TestClient,
    run_sources: RunSources,
    web: FakeWeb,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api.put("/api/profile", json=PROFILE)
    company = watch(
        db_session,
        Company(
            name="Acme",
            name_norm="acme",
            discovered_from="user",
            ats_type="workday",
            ats_token="acme/wd3/Site",
            detection_status="done",
            hints={},
        ),
    )
    api_url = "https://acme.wd3.myworkdayjobs.com/wday/cxs/acme/Site"
    web.add(
        f"{api_url}/jobs",
        {
            "total": 2,
            "jobPostings": [
                {
                    "title": "Python Developer",
                    "externalPath": "/job/a",
                    "locationsText": "Karlsruhe",
                },
                {"title": "Vue Developer", "externalPath": "/job/b", "locationsText": "Karlsruhe"},
            ],
        },
    )

    def detail(request: httpx.Request) -> httpx.Response:
        time.sleep(0.5)
        return httpx.Response(200, json={"jobPostingInfo": {"jobDescription": FULL_TEXT}})

    web.pages[f"{api_url}/job/a"] = detail
    web.pages[f"{api_url}/job/b"] = detail
    run_sources.client = web.client()
    monkeypatch.setattr(search_runner, "COMPANY_BUDGET", 0.4)

    stats = run(api)["stats"]["ats:workday"]

    # Without its details a posting would stay without full text for good, so it waits.
    assert (stats["new"], stats["errors"]) == (1, 1)
    db_session.refresh(company)
    assert company.last_error == search_runner.BUDGET_MESSAGE
    assert all(job.has_full_text for job in db_session.scalars(select(Job)))

    monkeypatch.setattr(search_runner, "COMPANY_BUDGET", 30.0)
    stats = run(api)["stats"]["ats:workday"]

    assert (stats["new"], stats["errors"]) == (1, 0)
    db_session.refresh(company)
    assert company.last_error is None
    jobs = list(db_session.scalars(select(Job)))
    assert len(jobs) == 2 and all(job.has_full_text for job in jobs)


def test_companies_api(api: TestClient, web: FakeWeb) -> None:
    web.add("https://acme.de/karriere", '<a href="https://acme.jobs.personio.de">Jobs</a>')

    added = api.post("/api/companies", json={"url": "acme.de/karriere", "name": "Acme GmbH"})

    assert added.status_code == 201, added.text
    company = added.json()
    assert (company["name"], company["status"], company["discovered_from"]) == (
        "Acme GmbH",
        "watch",
        "user",
    )
    assert (company["ats_type"], company["ats_token"]) == ("personio", "acme")

    page = api.get("/api/companies").json()
    assert (page["total"], page["with_feed"], page["watched"]) == (1, 1, 1)

    ignored = api.patch(f"/api/companies/{company['id']}", json={"status": "ignore"}).json()
    assert ignored["status"] == "ignore"
    assert api.get("/api/companies", params={"status": "watch"}).json()["items"] == []
    assert api.patch("/api/companies/999", json={"status": "watch"}).status_code == 404


def test_discovered_companies_without_feed_stay_hidden(
    api: TestClient, db_session: Session
) -> None:
    for name, origin, ats in [
        ("A", "github", "unknown"),
        ("B", "wikidata", "greenhouse"),
        ("C", "jobs", "unknown"),
    ]:
        company = Company(
            name=name, name_norm=name.lower(), discovered_from=origin, ats_type=ats, hints={}
        )
        db_session.add(company)
        db_session.flush()
        db_session.add(UserCompany(user_id=1, company_id=company.id))
    db_session.flush()

    names = [c["name"] for c in api.get("/api/companies").json()["items"]]

    assert sorted(names) == ["B", "C"]


def test_source_settings(api: TestClient) -> None:
    settings = api.get("/api/settings/sources").json()
    adzuna = next(s for s in settings["sources"] if s["key"] == "adzuna")
    assert adzuna["enabled"] and adzuna["missing"] == ["app_id", "app_key"]

    updated = api.put(
        "/api/settings/sources/adzuna", json={"config": {"app_id": "id1", "app_key": "s3cr3t-key"}}
    ).json()
    adzuna = next(s for s in updated["sources"] if s["key"] == "adzuna")
    assert adzuna["fields"] == {"app_id": "id1"}
    assert adzuna["secrets"] == {"app_key": True}
    assert adzuna["missing"] == []
    assert "s3cr3t-key" not in str(updated)

    off = api.put("/api/settings/sources/ba", json={"enabled": False}).json()
    assert next(s for s in off["sources"] if s["key"] == "ba")["enabled"] is False
    assert api.put("/api/settings/sources/nope", json={}).status_code == 404
    assert api.put("/api/settings/sources/ba", json={"config": {"x": "1"}}).status_code == 422

    general = api.put("/api/settings/general", json={"contact": "me@example.org"}).json()
    assert general["contact"] == "me@example.org"


def test_disabled_sources_are_not_searched(api: TestClient, fake_source: FakeSource) -> None:
    """The factory gets the settings; the real one leaves disabled sources out."""
    from applify.sources import build_sources
    from applify.sources.base import SourceConfig

    sources = build_sources({"ba": SourceConfig(enabled=False), "arbeitnow": SourceConfig()})
    assert [s.name for s in sources.sources] == ["service_bund"]
    assert [f.name for f in sources.feeds] == ["arbeitnow"]


def test_coverage(api: TestClient, fake_source: FakeSource, db_session: Session) -> None:
    api.put("/api/profile", json={**PROFILE, "exclude_keywords": ["Zeitarbeit"]})
    fake_source.postings = {
        "Fullstack Entwickler": [
            ba("1", "Fullstack Entwickler (m/w/d)", "Pixelwerk GmbH"),
            ba("2", "Python Entwickler Zeitarbeit", "Personal AG"),
        ]
    }
    run(api)
    db_session.add(
        Company(
            name="Bekannt GmbH",
            name_norm="bekannt",
            discovered_from="jobs",
            ats_type="unknown",
            hints={},
        )
    )
    db_session.flush()
    db_session.add(
        UserCompany(
            user_id=1,
            company_id=db_session.scalar(select(Company.id).where(Company.name_norm == "bekannt")),
        )
    )
    db_session.flush()

    samples = [
        {"company": "Pixelwerk", "title": "Full Stack Entwickler", "found_via": "stepstone"},
        {"url": "https://www.arbeitsagentur.de/jobsuche/jobdetail/2", "company": "x", "title": "y"},
        {"company": "Bekannt GmbH", "title": "Data Engineer"},
        {"company": "Völlig Neu GmbH", "title": "Frontend Developer"},
    ]
    results = [api.post("/api/coverage", json=s).json() for s in samples]

    assert results[0]["matched_sources"] == ["ba"] and results[0]["miss_reason"] is None
    assert results[1]["matched_job_id"] is not None and results[1]["miss_reason"] == "filter"
    assert results[2]["miss_reason"] == "adapter"
    assert results[3]["miss_reason"] == "discovery"

    coverage = api.get("/api/coverage").json()
    assert (coverage["total"], coverage["found"], coverage["visible"]) == (4, 2, 1)
    assert coverage["rate"] == 0.5
    assert coverage["by_source"] == {"ba": {"count": 2, "only": 2}}
    assert coverage["reasons"] == {"filter": 1, "adapter": 1, "discovery": 1}

    assert api.post("/api/coverage/check").json()["found"] == 2
    assert api.delete(f"/api/coverage/{results[3]['id']}").status_code == 204
    assert api.get("/api/coverage").json()["total"] == 3
