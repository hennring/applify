from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from applify.db.models import Job
from applify.db.session import get_session

router = APIRouter(prefix="/jobs", tags=["jobs"])

SessionDep = Annotated[Session, Depends(get_session)]


class SourceLink(BaseModel):
    source: str
    url: str


class JobOut(BaseModel):
    id: int
    title: str
    company: str
    location_raw: str
    population: int | None
    remote_type: str | None
    salary_min: int | None
    salary_max: int | None
    has_full_text: bool
    posted_at: datetime | None
    first_seen_at: datetime
    sources: list[SourceLink]


class JobDetail(JobOut):
    description: str
    lat: float | None
    lon: float | None


class JobPage(BaseModel):
    total: int
    items: list[JobOut]


@router.get("")
def list_jobs(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> JobPage:
    """Most recently published first; ranking per profile follows in M3."""
    jobs = session.scalars(
        select(Job)
        .options(selectinload(Job.sources))
        .order_by(Job.posted_at.desc().nulls_last(), Job.first_seen_at.desc(), Job.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return JobPage(
        total=session.scalar(select(func.count(Job.id))) or 0,
        items=[JobOut.model_validate(j, from_attributes=True) for j in jobs],
    )


@router.get("/{job_id}")
def get_job(job_id: int, session: SessionDep) -> JobDetail:
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Stelle nicht gefunden")
    return JobDetail.model_validate(job, from_attributes=True)
