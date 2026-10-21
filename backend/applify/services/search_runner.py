"""Search run (F5): every source, search term and profile location, as a background job."""

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from applify.db.models import SearchRun
from applify.services.cv_jobs import SessionFactory
from applify.services.geo import Gazetteer
from applify.services.job_store import find_source, store_posting
from applify.services.match_store import Scorer
from applify.services.profile_store import load_profile
from applify.services.search_terms import derive_search_terms
from applify.services.skills import SkillTaxonomy
from applify.sources.base import JobSource, SearchQuery, SourceError, SourcesFactory

log = logging.getLogger(__name__)

# Commit and update the progress every N postings while fetching details.
COMMIT_EVERY = 10
COUNTERS = ("found", "new", "duplicate", "known", "errors")


class RunConflict(Exception):
    pass


def running_run(session: Session, user_id: int) -> SearchRun | None:
    return session.scalar(
        select(SearchRun).where(SearchRun.user_id == user_id, SearchRun.status == "running")
    )


def create_run(session: Session, user_id: int) -> SearchRun:
    if running_run(session, user_id) is not None:
        raise RunConflict("Es läuft bereits ein Suchlauf")
    run = SearchRun(user_id=user_id, status="running", step="Startet …", stats={}, errors=[])
    session.add(run)
    session.commit()
    return run


def _location_label(query: SearchQuery) -> str:
    return f"{query.location} (+{query.radius_km} km)" if query.location else "ganz Deutschland"


class _Progress:
    def __init__(self, session: Session, run: SearchRun, sources: list[JobSource]) -> None:
        self.session = session
        self.run = run
        self.stats: dict[str, dict[str, Any]] = {
            s.name: {"label": s.label} | dict.fromkeys(COUNTERS, 0) for s in sources
        }
        self.errors: list[dict[str, str]] = []

    def save(self, progress: float, step: str) -> None:
        # JSONB columns only notice reassignment, not in-place changes.
        self.run.stats = {k: dict(v) for k, v in self.stats.items()}
        self.run.errors = list(self.errors)
        self.run.progress = min(progress, 1.0)
        self.run.step = step
        self.session.commit()

    def error(self, source: JobSource, query: SearchQuery | None, message: str) -> None:
        self.stats[source.name]["errors"] += 1
        context = f"„{query.term}“, {_location_label(query)}" if query else ""
        self.errors.append({"source": source.label, "query": context, "message": message})


def run_search(
    run_id: int,
    session_factory: SessionFactory,
    sources: SourcesFactory,
    gazetteer: Gazetteer,
    taxonomy: SkillTaxonomy,
) -> None:
    with session_factory() as session:
        run = session.get(SearchRun, run_id)
        if run is None:
            return
        try:
            _run(session, run, sources(), gazetteer, taxonomy)
        except Exception as exc:
            log.exception("search run %s failed", run_id)
            session.rollback()
            run.status, run.step = "failed", str(exc)[:300]
        else:
            run.status, run.step, run.progress = "done", "", 1.0
        run.finished_at = datetime.now(UTC)
        session.commit()


def _run(
    session: Session,
    run: SearchRun,
    sources: list[JobSource],
    gazetteer: Gazetteer,
    taxonomy: SkillTaxonomy,
) -> None:
    profile = load_profile(session, run.user_id)
    terms = derive_search_terms(profile)
    if not terms:
        raise ValueError("Keine Wunschrollen oder Pflicht-Skills im Profil")
    locations: list[tuple[str | None, int]] = [
        (loc.name, loc.radius_km) for loc in profile.locations
    ] or [(None, 0)]
    queries = [
        (source, SearchQuery(term, name, radius))
        for source in sources
        for name, radius in locations
        for term in terms
    ]
    scorer = Scorer(session, run.user_id, gazetteer, taxonomy)
    progress = _Progress(session, run, sources)
    seen: set[tuple[str, str]] = set()

    for i, (source, query) in enumerate(queries):
        step = f"{source.label}: „{query.term}“, {_location_label(query)}"
        progress.save(i / len(queries), step)
        try:
            postings = source.search(query)
        except SourceError as exc:
            progress.error(source, query, str(exc))
            continue
        postings = [p for p in postings if (p.source, p.external_id) not in seen]
        seen.update((p.source, p.external_id) for p in postings)
        stats = progress.stats[source.name]
        jobs = []
        for n, posting in enumerate(postings, 1):
            stats["found"] += 1
            # Details only for listings not stored yet; known ones keep what they have.
            if find_source(session, posting) is None:
                posting = source.complete(posting)
            job, outcome = store_posting(session, posting, gazetteer)
            jobs.append(job)
            stats[outcome] += 1
            if n % COMMIT_EVERY == 0:
                done = (i + n / len(postings)) / len(queries)
                progress.save(done, f"{step} – {n}/{len(postings)}")
        # Rated right away, so the list is usable while the run continues.
        scorer.score(jobs, run.id)
        progress.save((i + 1) / len(queries), step)


def fail_interrupted_runs(session: Session) -> None:
    """Runs execute in-process (D10); after a restart, 'running' runs will never finish."""
    session.execute(
        update(SearchRun)
        .where(SearchRun.status == "running")
        .values(status="failed", step="Abgebrochen durch Neustart", finished_at=datetime.now(UTC))
    )
    session.commit()
