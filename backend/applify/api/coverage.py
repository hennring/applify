from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from applify.db.models import CoverageSample, Job
from applify.db.session import get_session
from applify.services.coverage import REASONS, check_sample, summarize
from applify.users import get_current_user_id

router = APIRouter(prefix="/coverage", tags=["coverage"])

SessionDep = Annotated[Session, Depends(get_session)]
UserDep = Annotated[int, Depends(get_current_user_id)]


class SampleIn(BaseModel):
    url: str = Field("", max_length=1000)
    company: str = Field(min_length=1, max_length=300)
    title: str = Field(min_length=1, max_length=300)
    location: str = Field("", max_length=200)
    found_via: str = Field("", max_length=50)


class SampleOut(BaseModel):
    id: int
    url: str
    company: str
    title: str
    location: str
    found_via: str
    matched_job_id: int | None
    matched_title: str | None
    matched_sources: list[str]
    miss_reason: str | None
    checked_at: datetime | None
    created_at: datetime


class SourceShareOut(BaseModel):
    count: int
    only: int


class CoverageOut(BaseModel):
    total: int
    found: int
    visible: int
    rate: float | None
    by_source: dict[str, SourceShareOut]
    reasons: dict[str, int]
    reason_labels: dict[str, str]
    samples: list[SampleOut]


def _out(session: Session, sample: CoverageSample) -> SampleOut:
    job = session.get(Job, sample.matched_job_id) if sample.matched_job_id else None
    return SampleOut.model_validate(
        {
            **{c: getattr(sample, c) for c in SampleOut.model_fields if hasattr(sample, c)},
            "matched_title": job.title if job else None,
        }
    )


def _samples(session: Session, user_id: int) -> list[CoverageSample]:
    return list(
        session.scalars(
            select(CoverageSample)
            .where(CoverageSample.user_id == user_id)
            .order_by(CoverageSample.created_at.desc(), CoverageSample.id.desc())
        )
    )


@router.get("")
def get_coverage(session: SessionDep, user_id: UserDep) -> CoverageOut:
    samples = _samples(session, user_id)
    summary = summarize(samples)
    return CoverageOut(
        total=summary.total,
        found=summary.found,
        visible=summary.visible,
        rate=summary.rate,
        by_source={
            k: SourceShareOut(count=v.count, only=v.only) for k, v in summary.by_source.items()
        },
        reasons=summary.reasons,
        reason_labels=REASONS,
        samples=[_out(session, s) for s in samples],
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def add_sample(body: SampleIn, session: SessionDep, user_id: UserDep) -> SampleOut:
    sample = CoverageSample(user_id=user_id, **body.model_dump())
    session.add(sample)
    session.flush()
    check_sample(session, sample)
    session.commit()
    return _out(session, sample)


@router.post("/check")
def recheck(session: SessionDep, user_id: UserDep) -> CoverageOut:
    """Check every sample again, e.g. after a search run."""
    for sample in _samples(session, user_id):
        check_sample(session, sample)
    session.commit()
    return get_coverage(session, user_id)


@router.delete("/{sample_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sample(sample_id: int, session: SessionDep, user_id: UserDep) -> None:
    sample = session.get(CoverageSample, sample_id)
    if sample is None or sample.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Eintrag nicht gefunden")
    session.delete(sample)
    session.commit()
