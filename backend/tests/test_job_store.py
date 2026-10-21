from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from applify.db.models import Job, JobSource
from applify.services.geo import get_gazetteer
from applify.services.job_store import store_posting
from applify.sources.base import JobPosting

NOW = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)


def posting(**fields: object) -> JobPosting:
    values: dict[str, object] = {
        "source": "ba",
        "external_id": "1",
        "url": "https://example.org/1",
        "title": "Fullstack Entwickler (m/w/d)",
        "company": "Pixelwerk GmbH",
        "location_raw": "04109 Leipzig",
    }
    return JobPosting(**(values | fields))  # type: ignore[arg-type]


def store(session: Session, p: JobPosting, now: datetime = NOW) -> tuple[Job, str]:
    return store_posting(session, p, get_gazetteer(), now)


def test_new_job_is_normalized_and_enriched(db_session: Session) -> None:
    job, outcome = store(
        db_session,
        posting(description="Wir zahlen 55.000 - 65.000 € und bieten Homeoffice. " * 5),
    )
    assert outcome == "new"
    assert job.title == "Fullstack Entwickler"
    assert (job.company_norm, job.title_norm, job.city_norm) == (
        "pixelwerk",
        "fullstack entwickler",
        "leipzig",
    )
    # Salary from the text, coordinates from GeoNames; remote is only read from title/location.
    assert (job.salary_min, job.salary_max) == (55000, 65000)
    assert job.lat is not None and abs(job.lat - 51.34) < 0.1
    assert [s.source for s in job.sources] == ["ba"]


def test_same_listing_again_is_known(db_session: Session) -> None:
    first, _ = store(db_session, posting())
    again, outcome = store(db_session, posting(url="https://example.org/new"))
    assert outcome == "known"
    assert again.id == first.id
    assert again.sources[0].url == "https://example.org/new"


def test_exact_duplicate_from_another_source_is_merged(db_session: Session) -> None:
    first, _ = store(db_session, posting())
    other = posting(
        source="adzuna",
        external_id="a-9",
        title="Fullstack Entwickler*in",
        company="Pixelwerk",
        location_raw="Leipzig-Plagwitz",
        description="Ausführlicher Text. " * 20,
        has_full_text=True,
        salary_min=50000,
    )
    merged, outcome = store(db_session, other)
    assert outcome == "duplicate"
    assert merged.id == first.id
    assert sorted(s.source for s in merged.sources) == ["adzuna", "ba"]
    # Better data wins.
    assert merged.has_full_text
    assert merged.salary_min == 50000
    assert db_session.scalar(select(func.count(Job.id))) == 1


def test_fuzzy_duplicate(db_session: Session) -> None:
    first, _ = store(db_session, posting(title="Senior Fullstack Entwickler TypeScript"))
    similar = posting(
        source="arbeitnow", external_id="x", title="Senior Full Stack Entwickler (TypeScript)"
    )
    merged, outcome = store(db_session, similar)
    assert outcome == "duplicate"
    assert merged.id == first.id


def test_no_fuzzy_match_across_cities_or_after_30_days(db_session: Session) -> None:
    store(
        db_session,
        posting(title="Senior Fullstack Entwickler TypeScript"),
        NOW - timedelta(days=40),
    )
    _, outcome = store(
        db_session,
        posting(source="x", external_id="2", title="Senior Full Stack Entwickler (TypeScript)"),
    )
    assert outcome == "new"
    _, outcome = store(
        db_session,
        posting(
            source="x",
            external_id="3",
            title="Senior Full Stack Entwickler (TypeScript)",
            location_raw="Dresden",
        ),
    )
    assert outcome == "new"


def test_different_jobs_stay_apart(db_session: Session) -> None:
    store(db_session, posting(title="Senior Fullstack Entwickler TypeScript"))
    _, outcome = store(
        db_session, posting(external_id="2", title="Senior Frontend Entwickler TypeScript")
    )
    assert outcome == "new"
    assert db_session.scalar(select(func.count(JobSource.id))) == 2
