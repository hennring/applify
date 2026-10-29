from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import Select, func, select, update
from sqlalchemy.orm import Session, joinedload

from applify.api.jobs import JobDetail, JobOut
from applify.db.models import Job, JobMatch
from applify.db.session import get_session
from applify.services.geo import Gazetteer, get_gazetteer
from applify.services.match_store import Scorer
from applify.services.skills import SkillTaxonomy, get_taxonomy
from applify.users import get_current_user_id

router = APIRouter(prefix="/matches", tags=["matches"])

SessionDep = Annotated[Session, Depends(get_session)]
UserDep = Annotated[int, Depends(get_current_user_id)]
# Below this, pasted text is treated as a slip rather than a posting.
MIN_PASTED_TEXT = 100


class EvidenceOut(BaseModel):
    kind: Literal["hit", "miss", "unknown"]
    text: str


class ComponentOut(BaseModel):
    key: str
    label: str
    weight: int
    value: float | None
    points: float | None
    evidence: list[EvidenceOut]


class Breakdown(BaseModel):
    low_data: bool = False
    components: list[ComponentOut] = []


class MatchInfo(BaseModel):
    score: int
    excluded_reason: str | None
    status: str
    seen_at: datetime | None
    breakdown: Breakdown


class MatchOut(MatchInfo):
    job: JobOut


class MatchDetail(MatchInfo):
    job: JobDetail


class MatchPage(BaseModel):
    total: int
    new: int
    excluded: int
    items: list[MatchOut]


class PastedText(BaseModel):
    text: str = Field(min_length=MIN_PASTED_TEXT, max_length=100_000)


def _get_or_404(session: Session, user_id: int, job_id: int) -> JobMatch:
    match = session.scalar(
        select(JobMatch)
        .options(joinedload(JobMatch.job).selectinload(Job.sources))
        .where(JobMatch.user_id == user_id, JobMatch.job_id == job_id)
    )
    if match is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Stelle nicht gefunden")
    return match


@router.get("")
def list_matches(
    session: SessionDep,
    user_id: UserDep,
    only_new: bool = False,
    excluded: bool = False,
    sort: Literal["score", "date"] = "score",
    min_score: Annotated[int, Query(ge=0, le=100)] = 0,
    min_population: Annotated[int | None, Query(ge=0)] = None,
    max_population: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> MatchPage:
    """Ranked list (F11); hidden jobs only with excluded=true, each with its reason.

    min_population (inclusive) and max_population (exclusive) keep jobs in towns of that size;
    unknown places and remote-only jobs drop out.
    """
    base = select(JobMatch).where(JobMatch.user_id == user_id)
    visible = base.where(
        JobMatch.excluded_reason.is_not(None) if excluded else JobMatch.excluded_reason.is_(None)
    )
    if only_new:
        visible = visible.where(JobMatch.status == "new")
    if min_score:
        visible = visible.where(JobMatch.score >= min_score)
    if min_population is not None or max_population is not None:
        towns = select(Job.id).where(Job.population.is_not(None))
        if min_population is not None:
            towns = towns.where(Job.population >= min_population)
        if max_population is not None:
            towns = towns.where(Job.population < max_population)
        visible = visible.where(JobMatch.job_id.in_(towns))

    def count(query: Select[Any]) -> int:
        return session.scalar(select(func.count()).select_from(query.subquery())) or 0

    order = (
        (JobMatch.score.desc(), Job.posted_at.desc().nulls_last())
        if sort == "score"
        else (Job.posted_at.desc().nulls_last(), JobMatch.score.desc())
    )
    matches = session.scalars(
        visible.join(Job)
        .options(joinedload(JobMatch.job).selectinload(Job.sources))
        .order_by(*order, Job.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return MatchPage(
        total=count(visible),
        new=count(base.where(JobMatch.excluded_reason.is_(None), JobMatch.status == "new")),
        excluded=count(base.where(JobMatch.excluded_reason.is_not(None))),
        items=[MatchOut.model_validate(m, from_attributes=True) for m in matches],
    )


@router.get("/{job_id}")
def get_match(job_id: int, session: SessionDep, user_id: UserDep) -> MatchDetail:
    return MatchDetail.model_validate(_get_or_404(session, user_id, job_id), from_attributes=True)


@router.post("/{job_id}/seen")
def mark_seen(job_id: int, session: SessionDep, user_id: UserDep) -> MatchDetail:
    """Opened in the detail view: no longer new (F10)."""
    match = _get_or_404(session, user_id, job_id)
    if match.status == "new":
        match.status, match.seen_at = "seen", datetime.now(UTC)
        session.commit()
    return MatchDetail.model_validate(match, from_attributes=True)


@router.post("/seen", status_code=status.HTTP_204_NO_CONTENT)
def mark_all_seen(session: SessionDep, user_id: UserDep) -> None:
    session.execute(
        update(JobMatch)
        .where(JobMatch.user_id == user_id, JobMatch.status == "new")
        .values(status="seen", seen_at=datetime.now(UTC))
    )
    session.commit()


@router.put("/{job_id}/text")
def paste_text(
    job_id: int,
    body: PastedText,
    session: SessionDep,
    user_id: UserDep,
    gazetteer: Annotated[Gazetteer, Depends(get_gazetteer)],
    taxonomy: Annotated[SkillTaxonomy, Depends(get_taxonomy)],
) -> MatchDetail:
    """Posting text pasted by the user (F8); the job is rated again."""
    match = _get_or_404(session, user_id, job_id)
    job = match.job
    job.description, job.has_full_text, job.skills = body.text.strip(), True, None
    Scorer(session, user_id, gazetteer, taxonomy).score([job])
    session.commit()
    return MatchDetail.model_validate(match, from_attributes=True)
