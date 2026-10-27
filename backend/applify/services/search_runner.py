"""Search run (F5) as a background job, in stages:

1. sources searched per term and location (BA, Adzuna, service.bund.de),
2. feeds read as a whole (Arbeitnow),
3. companies: discovery (GitHub, Wikidata), ATS detection, careers pages (F7, F7a).
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from functools import partial
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from applify.db.models import Company, Job, JobSource, Profile, SearchRun, UserCompany
from applify.services.companies import CompanyRegistry, mark_checked
from applify.services.cv_jobs import SessionFactory
from applify.services.detect import apply_detection, detect
from applify.services.discovery import discover_github, discover_wikidata
from applify.services.geo import Gazetteer
from applify.services.job_store import find_source, store_posting
from applify.services.match_store import Scorer, profile_places
from applify.services.prefilter import Prefilter
from applify.services.profile_store import load_profile
from applify.services.raw_store import confirm_sightings, record_sightings
from applify.services.search_terms import derive_search_terms
from applify.services.skills import SkillTaxonomy
from applify.services.source_settings import BY_KEY, load_settings, save_setting
from applify.sources.ats import ADAPTERS, Feed
from applify.sources.base import (
    JobPosting,
    RunSources,
    SearchQuery,
    SourceConfig,
    SourceError,
    SourcesFactory,
)
from applify.sources.base import (
    JobSource as Source,
)
from applify.sources.http import PoliteClient
from applify.sources.jsonld import JsonLdCareers

log = logging.getLogger(__name__)

# Commit and update the progress every N postings while fetching details.
COMMIT_EVERY = 10
COUNTERS = ("found", "new", "duplicate", "known", "filtered", "errors")
# New companies whose careers page is looked for per run (§5.1); the rest waits.
DETECT_PER_RUN = 50
# Shares of the progress bar per stage when the company stage runs.
STAGES = {"search": 0.45, "feeds": 0.55, "discovery": 0.6, "detect": 0.75, "careers": 1.0}


class RunConflict(Exception):
    pass


class RunCanceled(Exception):
    """The user asked the run to stop."""


def request_cancel(session: Session, run: SearchRun) -> None:
    """Ask a running search run to stop; it does so at its next progress update."""
    if run.status == "running":
        run.cancel_requested = True
        session.commit()


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
    if query.remote:
        return "deutschlandweit, voll remote"
    return f"{query.location} (+{query.radius_km} km)" if query.location else "ganz Deutschland"


class _Progress:
    def __init__(self, session: Session, run: SearchRun) -> None:
        self.session = session
        self.run = run
        self.stats: dict[str, dict[str, Any]] = {}
        self.errors: list[dict[str, str]] = []
        self.start, self.end = 0.0, 1.0

    def source(self, key: str, label: str) -> dict[str, Any]:
        if key not in self.stats:
            self.stats[key] = {"label": label} | dict.fromkeys(COUNTERS, 0)
        return self.stats[key]

    def stage(self, start: float, end: float) -> None:
        self.start, self.end = start, end

    def save(self, fraction: float, step: str) -> None:
        # JSONB columns only notice reassignment, not in-place changes.
        self.run.stats = {k: dict(v) for k, v in self.stats.items()}
        self.run.errors = list(self.errors)
        self.run.progress = min(self.start + (self.end - self.start) * fraction, 1.0)
        self.run.step = step[:300]
        self.session.commit()

    def canceled(self) -> bool:
        # Read from the database: the request comes from another session.
        return bool(
            self.session.scalar(
                select(SearchRun.cancel_requested).where(SearchRun.id == self.run.id)
            )
        )

    def stop_if_canceled(self) -> None:
        if self.canceled():
            raise RunCanceled

    def error(self, key: str, label: str, context: str, message: str) -> None:
        self.source(key, label)["errors"] += 1
        self.errors.append({"source": label, "query": context, "message": message})


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
            _Run(session, run, sources, gazetteer, taxonomy).execute()
        except RunCanceled:
            # Everything stored so far stays; progress and stats show how far it got.
            run.status, run.step = "canceled", "Abgebrochen"
        except Exception as exc:
            log.exception("search run %s failed", run_id)
            session.rollback()
            run.status, run.step = "failed", str(exc)[:300]
        else:
            run.status, run.step, run.progress = "done", "", 1.0
        run.finished_at = datetime.now(UTC)
        session.commit()


class _Run:
    def __init__(
        self,
        session: Session,
        run: SearchRun,
        sources: SourcesFactory,
        gazetteer: Gazetteer,
        taxonomy: SkillTaxonomy,
    ) -> None:
        self.session = session
        self.run = run
        self.user_id = run.user_id
        self.gazetteer = gazetteer
        self.settings = load_settings(session, run.user_id)
        self.outside: RunSources = sources(self.settings)
        self.profile = load_profile(session, run.user_id)
        self.terms = derive_search_terms(self.profile)
        self.places = profile_places(session, run.user_id, gazetteer)
        self.prefilter = Prefilter(self.places, self.profile.remote_pref, gazetteer)
        self.scorer = Scorer(session, run.user_id, gazetteer, taxonomy)
        self.progress = _Progress(session, run)
        self.registry = CompanyRegistry(session, run.user_id)
        self.seen: set[tuple[str, str]] = set()
        self.fraction = 0.0  # progress within the current stage

    def execute(self) -> None:
        if not self.terms:
            raise ValueError("Keine Wunschrollen oder Pflicht-Skills im Profil")
        for source in self.outside.sources:
            self.progress.source(source.name, source.label)
        for feed in self.outside.feeds:
            self.progress.source(feed.name, feed.label)
        client = self.outside.client
        companies = client is not None and self.settings["careers"].enabled
        scale = 1.0 if companies else 1 / STAGES["feeds"]

        self.progress.stage(0, STAGES["search"] * scale)
        self._search()
        self.progress.stage(STAGES["search"] * scale, STAGES["feeds"] * scale)
        self._feeds()
        if client is not None and companies:
            self.progress.stage(STAGES["feeds"], STAGES["discovery"])
            self._discover(client)
            self.progress.stage(STAGES["discovery"], STAGES["detect"])
            self._detect(client)
            self.progress.stage(STAGES["detect"], STAGES["careers"])
            self._careers(client)

    # --- storing ------------------------------------------------------------------------

    def _ingest(
        self,
        key: str,
        postings: list[JobPosting],
        complete: Callable[[JobPosting], JobPosting],
        *,
        prefilter: bool,
        step: str,
        company: Company | None = None,
    ) -> None:
        """Dedup, prefilter, fetch details for new postings, store, link the company, score."""
        stats = self.progress.stats[key]
        postings = [p for p in postings if (p.source, p.external_id) not in self.seen]
        self.seen.update((p.source, p.external_id) for p in postings)
        jobs: list[Job] = []
        # As delivered, for the raw layer of the market analysis (§5.8).
        seen: list[tuple[JobPosting, int]] = []
        for n, posting in enumerate(postings, 1):
            stats["found"] += 1
            verdict = self.prefilter.check(posting) if prefilter else True
            if verdict is False:
                stats["filtered"] += 1
                continue
            # Details only for listings not stored yet; known ones keep what they have.
            if find_source(self.session, posting) is None:
                posting = complete(posting)
                if verdict is None and not self.prefilter.check(posting):
                    stats["filtered"] += 1
                    continue
            job, outcome = store_posting(self.session, posting, self.gazetteer)
            if company is not None:
                job.company_id = job.company_id or company.id
            else:
                self.registry.attach(job, posting)
            jobs.append(job)
            seen.append((posting, job.id))
            stats[outcome] += 1
            if n % COMMIT_EVERY == 0:
                self.progress.save(self.fraction, f"{step} – {n}/{len(postings)}")
                if self.progress.canceled():
                    break
        record_sightings(self.session, self.run.id, seen, datetime.now(UTC))
        # Rated right away, so the list is usable while the run continues.
        self.scorer.score(jobs, self.run.id)
        self.progress.stop_if_canceled()

    def _step(self, done: float, step: str) -> None:
        self.fraction = done
        self.progress.save(done, step)
        self.progress.stop_if_canceled()

    # --- stage 1 and 2: job sources ------------------------------------------------------

    def _search(self) -> None:
        locations: list[tuple[str | None, int]] = [
            (loc.name, loc.radius_km) for loc in self.profile.locations
        ] or [(None, 0)]
        queries: list[tuple[Source, SearchQuery]] = []
        for source in self.outside.sources:
            # Sources that ignore the location are searched once per term.
            places = locations if getattr(source, "located", True) else [(None, 0)]
            queries += [
                (source, SearchQuery(term, name, radius))
                for name, radius in places
                for term in self.terms
            ]
            # Fully remote jobs may be anywhere; the place search only finds those nearby.
            if (
                self.profile.remote_pref == "remote"
                and self.profile.locations
                and getattr(source, "remote_search", False)
            ):
                queries += [
                    (source, SearchQuery(term, None, 0, remote=True)) for term in self.terms
                ]
        for i, (source, query) in enumerate(queries):
            step = f"{source.label}: „{query.term}“, {_location_label(query)}"
            self._step(i / len(queries), step)
            try:
                postings = source.search(query)
            except SourceError as exc:
                context = f"„{query.term}“, {_location_label(query)}"
                self.progress.error(source.name, source.label, context, str(exc))
                continue
            prefilter = not getattr(source, "located", True)
            self._ingest(source.name, postings, source.complete, prefilter=prefilter, step=step)
        self._step(1, "Suche abgeschlossen")

    def _feeds(self) -> None:
        feeds = self.outside.feeds
        for i, feed in enumerate(feeds):
            self._step(i / len(feeds), f"{feed.label}: lädt …")
            try:
                postings = feed.fetch()
            except SourceError as exc:
                self.progress.error(feed.name, feed.label, "", str(exc))
                continue
            self._ingest(feed.name, postings, feed.complete, prefilter=True, step=feed.label)
        self._step(1, "Feeds abgeschlossen")

    # --- stage 3: companies --------------------------------------------------------------

    def _discover(self, client: PoliteClient) -> None:
        now = datetime.now(UTC)
        steps = [("github", discover_github), ("wikidata", discover_wikidata)]
        for i, (key, discover) in enumerate(steps):
            config: SourceConfig = self.settings[key]
            if not config.enabled or not self.places:
                continue
            label = BY_KEY[key].label
            self._step(i / len(steps), f"{label}: sucht Firmen …")
            stats = self.progress.source(key, label)
            try:
                new_config, added = discover(client, self.registry, self.places, config, now)
            except SourceError as exc:
                self.progress.error(key, label, "", str(exc))
                continue
            stats["found"] += added
            save_setting(self.session, self.user_id, key, **new_config)
            self.session.commit()

    def _detect(self, client: PoliteClient) -> None:
        job_count = (
            select(func.count(Job.id))
            .where(Job.company_id == Company.id)
            .correlate(Company)
            .scalar_subquery()
        )
        pending = list(
            self.session.scalars(
                select(Company)
                .join(UserCompany, UserCompany.company_id == Company.id)
                .where(
                    UserCompany.user_id == self.user_id,
                    UserCompany.status != "ignore",
                    Company.detection_status == "pending",
                )
                .order_by(
                    (Company.discovered_from == "user").desc(),
                    Company.website.is_(None),
                    job_count.desc(),
                    Company.id,
                )
                .limit(DETECT_PER_RUN)
            )
        )
        for i, company in enumerate(pending):
            self._step(i / max(len(pending), 1), f"Karriereseite suchen: {company.name}")
            try:
                found = detect(client, company)
            except SourceError as exc:  # unexpected; detect handles page errors itself
                found = None
                company.detection_status, company.last_error = "failed", str(exc)[:500]
            if found is not None:
                apply_detection(company, found)
            self.session.commit()

    def _careers(self, client: PoliteClient) -> None:
        profile_changed = self.session.scalar(
            select(Profile.updated_at).where(Profile.user_id == self.user_id)
        )
        companies = list(
            self.session.scalars(
                select(Company)
                .join(UserCompany, UserCompany.company_id == Company.id)
                .where(
                    UserCompany.user_id == self.user_id,
                    UserCompany.status != "ignore",
                    Company.ats_type != "unknown",
                )
                .order_by(Company.name_norm)
            )
        )
        jsonld = JsonLdCareers()
        for i, company in enumerate(companies):
            step = f"Karriereseite: {company.name}"
            self._step(i / max(len(companies), 1), step)
            now = datetime.now(UTC)
            if company.ats_type == "jsonld":
                key, label = "jsonld", jsonld.label
            else:
                adapter = ADAPTERS[company.ats_type]
                key, label = f"ats:{adapter.type}", adapter.label
            self.progress.source(key, label)
            complete: Callable[[JobPosting], JobPosting] = _unchanged
            # Postings still listed without being delivered again (raw layer, §5.8).
            listed: set[str] = set()
            unchanged = False
            try:
                if company.ats_type == "jsonld":
                    known = set(
                        self.session.scalars(
                            select(JobSource.url)
                            .join(Job)
                            .where(Job.company_id == company.id, JobSource.source == "jsonld")
                        )
                    )
                    postings = jsonld.fetch(
                        client,
                        company.careers_url or company.website or "",
                        company.name,
                        known,
                        listed,
                    )
                else:
                    # A changed profile may let through postings the prefilter dropped before.
                    fresh = (
                        company.last_checked_at is not None
                        and profile_changed is not None
                        and profile_changed < company.last_checked_at
                    )
                    feed = Feed(
                        company.ats_token or "",
                        company.name,
                        self.terms,
                        etag=company.etag if fresh else None,
                    )
                    postings = adapter.fetch(client, feed)
                    company.etag, unchanged = feed.etag, feed.unchanged
                    complete = partial(adapter.complete, client)
            except (SourceError, ValueError, KeyError) as exc:
                message = str(exc) or type(exc).__name__
                mark_checked(company, now, message)
                self.progress.error(key, label, company.name, message)
                self.session.commit()
                continue
            mark_checked(company, now)
            if listed or unchanged:
                self._confirm(company, key, listed if listed else None)
            self._ingest(key, postings, complete, prefilter=True, step=step, company=company)
            self.session.commit()
        self._step(1, "Karriereseiten abgeschlossen")

    def _confirm(self, company: Company, key: str, urls: set[str] | None) -> None:
        """The company's stored postings from this source, or those with the given URLs."""
        query = (
            select(JobSource).join(Job).where(Job.company_id == company.id, JobSource.source == key)
        )
        if urls is not None:
            query = query.where(JobSource.url.in_(urls))
        sources = list(self.session.scalars(query))
        confirm_sightings(self.session, self.run.id, sources, datetime.now(UTC))


def _unchanged(posting: JobPosting) -> JobPosting:
    return posting


def fail_interrupted_runs(session: Session) -> None:
    """Runs execute in-process (D10); after a restart, 'running' runs will never finish."""
    session.execute(
        update(SearchRun)
        .where(SearchRun.status == "running")
        .values(status="failed", step="Abgebrochen durch Neustart", finished_at=datetime.now(UTC))
    )
    session.commit()
