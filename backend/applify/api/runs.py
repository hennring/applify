from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from applify.db.models import SearchRun
from applify.db.session import get_session, get_session_factory
from applify.services.background import TaskRunner, get_search_runner
from applify.services.cv_jobs import SessionFactory
from applify.services.geo import Gazetteer, get_gazetteer
from applify.services.search_runner import RunConflict, create_run, run_search
from applify.sources import get_sources_factory
from applify.sources.base import SourcesFactory
from applify.users import get_current_user_id

router = APIRouter(prefix="/runs", tags=["runs"])

SessionDep = Annotated[Session, Depends(get_session)]
UserDep = Annotated[int, Depends(get_current_user_id)]


class SourceStats(BaseModel):
    label: str
    found: int
    new: int
    duplicate: int
    known: int
    errors: int


class RunError(BaseModel):
    source: str
    query: str
    message: str


class RunOut(BaseModel):
    id: int
    status: str
    progress: float
    step: str
    stats: dict[str, SourceStats]
    errors: list[RunError]
    started_at: datetime
    finished_at: datetime | None

    @classmethod
    def of(cls, run: SearchRun) -> "RunOut":
        return cls.model_validate(run, from_attributes=True)


def _get_or_404(session: Session, user_id: int, run_id: int) -> SearchRun:
    run = session.get(SearchRun, run_id)
    if run is None or run.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Suchlauf nicht gefunden")
    return run


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def start_run(
    session: SessionDep,
    user_id: UserDep,
    runner: Annotated[TaskRunner, Depends(get_search_runner)],
    session_factory: Annotated[SessionFactory, Depends(get_session_factory)],
    sources: Annotated[SourcesFactory, Depends(get_sources_factory)],
    gazetteer: Annotated[Gazetteer, Depends(get_gazetteer)],
) -> RunOut:
    try:
        run = create_run(session, user_id)
    except RunConflict as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    runner(run_search, run.id, session_factory, sources, gazetteer)
    session.refresh(run)
    return RunOut.of(run)


@router.get("/latest")
def latest_run(session: SessionDep, user_id: UserDep) -> RunOut | None:
    run = session.scalar(
        select(SearchRun)
        .where(SearchRun.user_id == user_id)
        .order_by(SearchRun.started_at.desc(), SearchRun.id.desc())
        .limit(1)
    )
    return RunOut.of(run) if run else None


@router.get("/{run_id}")
def get_run(run_id: int, session: SessionDep, user_id: UserDep) -> RunOut:
    return RunOut.of(_get_or_404(session, user_id, run_id))
