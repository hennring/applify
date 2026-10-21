"""Store match results per user and job; rescore when the profile or a job changes."""

from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from applify.db.models import Job, JobMatch, Profile
from applify.schemas.profile import ProfileData
from applify.services.geo import Gazetteer, get_gazetteer
from applify.services.matching import JobFacts, ProfilePlace, match_job
from applify.services.profile_store import load_profile
from applify.services.skills import SkillTaxonomy, get_taxonomy


def job_skills(job: Job, taxonomy: SkillTaxonomy) -> list[str]:
    """Canonical skills in title and text, scanned once per text version."""
    if job.skills is None:
        mentions = taxonomy.find_mentions(f"{job.title}\n{job.description}")
        job.skills = [m.skill.name for m in mentions]
    return job.skills


def facts(job: Job, taxonomy: SkillTaxonomy) -> JobFacts:
    return JobFacts(
        title=job.title,
        company=job.company,
        description=job.description,
        skills=tuple(job_skills(job, taxonomy)),
        lat=job.lat,
        lon=job.lon,
        remote_type=job.remote_type,
        salary_min=job.salary_min,
        salary_max=job.salary_max,
        has_full_text=job.has_full_text,
    )


def profile_places(session: Session, user_id: int, gazetteer: Gazetteer) -> list[ProfilePlace]:
    row = session.scalar(select(Profile).where(Profile.user_id == user_id))
    places = []
    for location in row.locations if row else []:
        lat, lon = location.lat, location.lon
        if lat is None or lon is None:
            if (place := gazetteer.locate(location.name)) is None:
                continue
            lat, lon = place.lat, place.lon
        places.append(ProfilePlace(location.name, lat, lon, location.radius_km))
    return places


class Scorer:
    """Rates jobs for one user; loads profile, places and taxonomy once."""

    def __init__(
        self, session: Session, user_id: int, gazetteer: Gazetteer, taxonomy: SkillTaxonomy
    ) -> None:
        self.session = session
        self.user_id = user_id
        self.taxonomy = taxonomy
        self.profile: ProfileData = load_profile(session, user_id)
        self.places = profile_places(session, user_id, gazetteer)

    def score(self, jobs: Iterable[Job], run_id: int | None = None) -> None:
        jobs = list(jobs)
        existing = {
            m.job_id: m
            for m in self.session.scalars(
                select(JobMatch).where(
                    JobMatch.user_id == self.user_id, JobMatch.job_id.in_([j.id for j in jobs])
                )
            )
        }
        now = datetime.now(UTC)
        for job in jobs:
            result = match_job(facts(job, self.taxonomy), self.profile, self.places, self.taxonomy)
            match = existing.get(job.id)
            if match is None:
                match = JobMatch(user_id=self.user_id, job_id=job.id, status="new", run_id=run_id)
                self.session.add(match)
            match.score = result.score
            match.excluded_reason = result.excluded_reason
            match.breakdown = result.breakdown()
            match.scored_at = now
        self.session.flush()

    def rescore_all(self) -> int:
        """After a profile change: every job this user has a match for."""
        jobs = list(
            self.session.scalars(select(Job).join(JobMatch).where(JobMatch.user_id == self.user_id))
        )
        self.score(jobs)
        return len(jobs)


def rescore_user(session: Session, user_id: int) -> int:
    """Rescore all matches of a user, e.g. after the profile was saved."""
    return Scorer(session, user_id, get_gazetteer(), get_taxonomy()).rescore_all()
