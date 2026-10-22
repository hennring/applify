"""Store postings as jobs, merging duplicates across sources (§5.2, F9)."""

from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from applify.db.models import Job, JobSource
from applify.services.geo import Gazetteer
from applify.services.normalize import (
    REMOTE_LOCATION,
    clean_title,
    detect_remote,
    fingerprint,
    normalize_city,
    normalize_company,
    normalize_title,
    parse_salary,
)
from applify.sources.base import JobPosting

FUZZY_THRESHOLD = 0.85
FUZZY_WINDOW = timedelta(days=30)

# new: first time seen; duplicate: merged into a job from another listing;
# known: this listing was stored before.
Outcome = Literal["new", "duplicate", "known"]


def enrich(posting: JobPosting, gazetteer: Gazetteer) -> JobPosting:
    """Fill what the source left open from the text and the offline geo data."""
    if posting.salary_min is None and posting.salary_max is None and posting.description:
        posting.salary_min, posting.salary_max = parse_salary(posting.description)
    if posting.remote_type is None:
        if REMOTE_LOCATION.search(posting.location_raw):
            posting.remote_type = "remote"
        else:
            posting.remote_type = detect_remote(f"{posting.title}\n{posting.location_raw}")
    place = gazetteer.locate(posting.location_raw) if posting.lat is None else None
    if place is not None:
        posting.lat, posting.lon = place.lat, place.lon
    return posting


def find_source(session: Session, posting: JobPosting) -> JobSource | None:
    return session.scalar(
        select(JobSource).where(
            JobSource.source == posting.source, JobSource.external_id == posting.external_id
        )
    )


def _city(posting: JobPosting) -> str:
    # "04109 Leipzig" → "leipzig"
    return normalize_city(posting.location_raw.lstrip("0123456789 "))


def find_duplicate(session: Session, posting: JobPosting, now: datetime) -> Job | None:
    company = normalize_company(posting.company)
    title = normalize_title(posting.title, posting.company)
    city = _city(posting)
    exact = session.scalar(
        select(Job)
        .where(Job.fingerprint == fingerprint(posting.company, posting.title, city))
        .order_by(Job.id)
        .limit(1)
    )
    if exact is not None or not company or not title:
        return exact
    similarity = func.similarity(Job.company_norm + " " + Job.title_norm, f"{company} {title}")
    query = select(Job).where(
        # Trigram prefilter on the company (uses the GIN index), then the full key.
        Job.company_norm.op("%")(company),
        Job.first_seen_at >= now - FUZZY_WINDOW,
        similarity >= FUZZY_THRESHOLD,
    )
    if city:
        query = query.where(or_(Job.city_norm == city, Job.city_norm == ""))
    return session.scalar(query.order_by(similarity.desc(), Job.id).limit(1))


def merge(job: Job, posting: JobPosting) -> None:
    """Better data wins: full text over short info, known over unknown values."""
    if posting.has_full_text and (
        not job.has_full_text or len(posting.description) > len(job.description)
    ):
        job.description, job.has_full_text = posting.description, True
        job.skills = None  # rescan on the next scoring
    elif not job.description and posting.description:
        job.description, job.skills = posting.description, None
    if job.salary_min is None and job.salary_max is None:
        job.salary_min, job.salary_max = posting.salary_min, posting.salary_max
    if job.lat is None and posting.lat is not None:
        job.lat, job.lon = posting.lat, posting.lon
    job.remote_type = job.remote_type or posting.remote_type
    job.location_raw = job.location_raw or posting.location_raw
    if posting.posted_at and (job.posted_at is None or posting.posted_at < job.posted_at):
        job.posted_at = posting.posted_at


def _source_row(posting: JobPosting, now: datetime) -> JobSource:
    return JobSource(
        source=posting.source,
        external_id=posting.external_id,
        url=posting.url,
        raw=posting.raw,
        fetched_at=now,
    )


def store_posting(
    session: Session, posting: JobPosting, gazetteer: Gazetteer, now: datetime | None = None
) -> tuple[Job, Outcome]:
    now = now or datetime.now(UTC)
    posting = enrich(posting, gazetteer)
    if (source := find_source(session, posting)) is not None:
        merge(source.job, posting)
        source.url, source.raw, source.fetched_at = posting.url, posting.raw, now
        return source.job, "known"

    if (job := find_duplicate(session, posting, now)) is not None:
        merge(job, posting)
        job.sources.append(_source_row(posting, now))
        session.flush()
        return job, "duplicate"

    city = _city(posting)
    job = Job(
        title=clean_title(posting.title, posting.company)[:300],
        company=posting.company[:300],
        location_raw=posting.location_raw[:300],
        lat=posting.lat,
        lon=posting.lon,
        remote_type=posting.remote_type,
        salary_min=posting.salary_min,
        salary_max=posting.salary_max,
        description=posting.description,
        has_full_text=posting.has_full_text,
        posted_at=posting.posted_at,
        company_norm=normalize_company(posting.company)[:300],
        title_norm=normalize_title(posting.title, posting.company)[:300],
        city_norm=city[:100],
        fingerprint=fingerprint(posting.company, posting.title, city),
        first_seen_at=now,
        sources=[_source_row(posting, now)],
    )
    session.add(job)
    session.flush()
    return job, "new"
