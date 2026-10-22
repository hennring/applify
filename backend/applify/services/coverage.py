"""Coverage check (F10a, §5.7): are jobs the user found elsewhere in Applify's stock?"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from applify.db.models import Company, CoverageSample, Job, JobMatch, JobSource, UserCompany
from applify.services.job_store import find_duplicate
from applify.services.normalize import normalize_company, normalize_title
from applify.sources.base import JobPosting

# User-typed titles differ more from the posting than two sources of the same posting do.
WINDOW = timedelta(days=45)
COMPANY_SIMILARITY = 0.6
TITLE_SIMILARITY = 0.5
REASONS = {
    "discovery": "Firma unbekannt – Lücke in der Discovery",
    "adapter": "Firma bekannt, aber kein Feed/JSON-LD erkannt",
    "missing": "Firma wird abgerufen, Stelle fehlt – Adapter oder Vorfilter",
    "filter": "Gefunden, aber ausgeblendet – Filter zu streng",
}


def _url_key(url: str) -> str:
    parts = urlsplit(url.strip())
    return f"{parts.netloc.lower().removeprefix('www.')}{parts.path.rstrip('/')}"


def find_job(session: Session, sample: CoverageSample, now: datetime) -> Job | None:
    if sample.url and (key := _url_key(sample.url)):
        # "_" in the pattern matches any character; the exact comparison follows.
        for source in session.scalars(select(JobSource).where(JobSource.url.ilike(f"%{key}%"))):
            if _url_key(source.url) == key:
                return source.job
    posting = JobPosting(
        source="coverage",
        external_id="",
        url="",
        title=sample.title,
        company=sample.company,
        location_raw=sample.location,
    )
    if job := find_duplicate(session, posting, now):
        return job
    company, title = normalize_company(sample.company), normalize_title(sample.title)
    if not company or not title:
        return None
    score = func.similarity(Job.company_norm, company) + func.similarity(Job.title_norm, title)
    return session.scalar(
        select(Job)
        .where(
            func.similarity(Job.company_norm, company) >= COMPANY_SIMILARITY,
            func.similarity(Job.title_norm, title) >= TITLE_SIMILARITY,
            Job.first_seen_at >= now - WINDOW,
        )
        .order_by(score.desc(), Job.id)
        .limit(1)
    )


def _known_company(session: Session, user_id: int, name: str) -> Company | None:
    norm = normalize_company(name)
    if not norm:
        return None
    return session.scalar(
        select(Company)
        .join(UserCompany, UserCompany.company_id == Company.id)
        .where(
            UserCompany.user_id == user_id,
            func.similarity(Company.name_norm, norm) >= COMPANY_SIMILARITY,
        )
        .order_by(func.similarity(Company.name_norm, norm).desc())
        .limit(1)
    )


def check_sample(session: Session, sample: CoverageSample, now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
    sample.checked_at = now
    job = find_job(session, sample, now)
    if job is not None:
        sample.matched_job_id = job.id
        sample.matched_sources = sorted({s.source for s in job.sources})
        match = session.scalar(
            select(JobMatch).where(JobMatch.user_id == sample.user_id, JobMatch.job_id == job.id)
        )
        sample.miss_reason = "filter" if match is not None and match.excluded_reason else None
        return
    sample.matched_job_id, sample.matched_sources = None, []
    company = _known_company(session, sample.user_id, sample.company)
    if company is None:
        sample.miss_reason = "discovery"
    elif company.ats_type == "unknown":
        sample.miss_reason = "adapter"
    else:
        sample.miss_reason = "missing"


@dataclass
class SourceShare:
    count: int = 0  # samples this source delivered
    only: int = 0  # samples only this source delivered


@dataclass
class Summary:
    total: int = 0
    found: int = 0
    visible: int = 0
    rate: float | None = None
    by_source: dict[str, SourceShare] = field(default_factory=dict)
    reasons: dict[str, int] = field(default_factory=dict)


def summarize(samples: list[CoverageSample]) -> Summary:
    summary = Summary(total=len(samples))
    for sample in samples:
        if sample.matched_job_id is not None:
            summary.found += 1
            summary.visible += sample.miss_reason is None
            groups = {
                "careers" if s.startswith(("ats:", "jsonld")) else s for s in sample.matched_sources
            }
            for source in groups:
                share = summary.by_source.setdefault(source, SourceShare())
                share.count += 1
                share.only += len(groups) == 1
        if sample.miss_reason:
            summary.reasons[sample.miss_reason] = summary.reasons.get(sample.miss_reason, 0) + 1
    if summary.total:
        summary.rate = summary.found / summary.total
    return summary
