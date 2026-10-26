"""Raw layer of the market analysis (§5.8, D21): what each search run saw, append-only."""

import hashlib
import json
from datetime import datetime

from sqlalchemy import select, tuple_
from sqlalchemy.dialects.postgresql import distinct_on, insert
from sqlalchemy.orm import Session

from applify.db.models import JobSighting, JobSource, JobVersion
from applify.sources.base import JobPosting


def content_hash(posting: JobPosting) -> str:
    """Hash over the posting's content, not its raw payload.

    Payloads carry query-dependent fields (e.g. the BA's distance to the searched place),
    which would create a new version on every run.
    """
    content = {
        "source": posting.source,
        "external_id": posting.external_id,
        "title": posting.title,
        "company": posting.company,
        "location_raw": posting.location_raw,
        "remote_type": posting.remote_type,
        "salary_min": posting.salary_min,
        "salary_max": posting.salary_max,
        "description": posting.description,
        "has_full_text": posting.has_full_text,
        "posted_at": posting.posted_at.isoformat() if posting.posted_at else None,
    }
    return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()


def record_sightings(
    session: Session, run_id: int, seen: list[tuple[JobPosting, int]], now: datetime
) -> None:
    """Postings as delivered in this run, each with the job it was stored under."""
    if not seen:
        return
    hashes = [content_hash(posting) for posting, _ in seen]
    versions = {
        digest: {
            "content_hash": digest,
            "source": posting.source,
            "external_id": posting.external_id,
            "job_id": job_id,
            "title": posting.title,
            "company": posting.company,
            "location_raw": posting.location_raw,
            "remote_type": posting.remote_type,
            "salary_min": posting.salary_min,
            "salary_max": posting.salary_max,
            "description": posting.description,
            "has_full_text": posting.has_full_text,
            "posted_at": posting.posted_at,
            "payload": posting.raw,
            "first_seen_at": now,
        }
        for digest, (posting, job_id) in zip(hashes, seen, strict=True)
    }
    session.execute(insert(JobVersion).values(list(versions.values())).on_conflict_do_nothing())
    session.execute(
        insert(JobSighting).values(
            [
                {
                    "run_id": run_id,
                    "seen_at": now,
                    "source": posting.source,
                    "external_id": posting.external_id,
                    "job_id": job_id,
                    "content_hash": digest,
                }
                for digest, (posting, job_id) in zip(hashes, seen, strict=True)
            ]
        )
    )


def confirm_sightings(
    session: Session, run_id: int, sources: list[JobSource], now: datetime
) -> None:
    """Postings still listed but not delivered again (unchanged feed, known JSON-LD page).

    They are seen with their last known content.
    """
    if not sources:
        return
    keys = [(s.source, s.external_id) for s in sources]
    latest = (
        select(JobSighting.source, JobSighting.external_id, JobSighting.content_hash)
        .where(tuple_(JobSighting.source, JobSighting.external_id).in_(keys))
        .ext(distinct_on(JobSighting.source, JobSighting.external_id))
        .order_by(JobSighting.source, JobSighting.external_id, JobSighting.seen_at.desc())
    )
    last = {
        (source, external_id): digest for source, external_id, digest in session.execute(latest)
    }
    rows = [
        {
            "run_id": run_id,
            "seen_at": now,
            "source": s.source,
            "external_id": s.external_id,
            "job_id": s.job_id,
            "content_hash": last[(s.source, s.external_id)],
        }
        for s in sources
        if (s.source, s.external_id) in last
    ]
    if rows:
        session.execute(insert(JobSighting).values(rows))
