from datetime import datetime
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import ColumnElement, Row, Select, and_, func, or_, select
from sqlalchemy.orm import Session

from applify.db.models import Company, Job, JobMatch, UserCompany
from applify.db.session import get_session
from applify.services.companies import CompanyRegistry, registered_domain
from applify.services.detect import apply_detection, detect
from applify.services.source_settings import load_settings
from applify.sources import ClientFactory, get_client_factory
from applify.sources.ats import find_ats
from applify.users import get_current_user_id

router = APIRouter(prefix="/companies", tags=["companies"])

SessionDep = Annotated[Session, Depends(get_session)]
UserDep = Annotated[int, Depends(get_current_user_id)]
ClientFactoryDep = Annotated[ClientFactory, Depends(get_client_factory)]
Status = Literal["candidate", "watch", "ignore"]


class CompanyOut(BaseModel):
    id: int
    name: str
    website: str | None
    careers_url: str | None
    ats_type: str
    ats_token: str | None
    discovered_from: str
    detection_status: str
    last_checked_at: datetime | None
    last_error: str | None
    status: Status
    jobs: int
    # Jobs of this company in the user's list (not hidden by a hard filter).
    visible_jobs: int


class CompanyPage(BaseModel):
    total: int
    with_feed: int
    watched: int
    pending: int
    items: list[CompanyOut]


class CompanyIn(BaseModel):
    url: str = Field(min_length=4, max_length=1000)
    name: str = Field("", max_length=300)


class CompanyPatch(BaseModel):
    status: Status


def _visible() -> ColumnElement[bool]:
    # Discovery finds many companies; without a careers page they would only be noise (§5.1).
    return or_(Company.discovered_from.in_(("jobs", "user")), Company.ats_type != "unknown")


def _query(user_id: int) -> Select[Company, UserCompany, Any, Any]:
    jobs = (
        select(
            Job.company_id,
            func.count(Job.id).label("jobs"),
            func.count(JobMatch.id).label("visible"),
        )
        .outerjoin(
            JobMatch,
            and_(
                JobMatch.job_id == Job.id,
                JobMatch.user_id == user_id,
                JobMatch.excluded_reason.is_(None),
            ),
        )
        .group_by(Job.company_id)
        .subquery()
    )
    return (
        select(
            Company,
            UserCompany,
            func.coalesce(jobs.c.jobs, 0),
            func.coalesce(jobs.c.visible, 0),
        )
        .join(UserCompany, UserCompany.company_id == Company.id)
        .outerjoin(jobs, jobs.c.company_id == Company.id)
        .where(UserCompany.user_id == user_id, _visible())
    )


def _out(row: Row[Company, UserCompany, Any, Any]) -> CompanyOut:
    company, link, jobs, visible = row
    return CompanyOut.model_validate(
        {
            **{c: getattr(company, c) for c in CompanyOut.model_fields if hasattr(company, c)},
            "id": company.id,
            "status": link.status,
            "jobs": jobs,
            "visible_jobs": visible,
        }
    )


def _get(session: Session, user_id: int, company_id: int) -> CompanyOut:
    row = session.execute(_query(user_id).where(Company.id == company_id)).one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Firma nicht gefunden")
    return _out(row)


@router.get("")
def list_companies(
    session: SessionDep,
    user_id: UserDep,
    status_filter: Annotated[Status | None, Query(alias="status")] = None,
    feed: Annotated[bool, Query(description="Only companies with a detected feed")] = False,
    q: Annotated[str, Query(max_length=100)] = "",
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CompanyPage:
    base = _query(user_id)
    counts = session.execute(
        select(
            func.count(),
            func.count().filter(Company.ats_type != "unknown"),
            func.count().filter(UserCompany.status == "watch"),
            func.count().filter(Company.detection_status == "pending"),
        )
        .select_from(Company)
        .join(UserCompany, UserCompany.company_id == Company.id)
        .where(UserCompany.user_id == user_id, _visible())
    ).one()
    if status_filter:
        base = base.where(UserCompany.status == status_filter)
    if feed:
        base = base.where(Company.ats_type != "unknown")
    if q.strip():
        base = base.where(Company.name.ilike(f"%{q.strip()}%"))
    rows = session.execute(
        base.order_by(
            (UserCompany.status == "watch").desc(),
            (Company.ats_type != "unknown").desc(),
            func.lower(Company.name),
        )
        .limit(limit)
        .offset(offset)
    ).all()
    return CompanyPage(
        total=counts[0],
        with_feed=counts[1],
        watched=counts[2],
        pending=counts[3],
        items=[_out(row) for row in rows],
    )


def _name_from_url(url: str) -> str:
    if hit := find_ats(url):
        return hit[1].split("/")[0]
    host = urlsplit(url if "://" in url else f"https://{url}").netloc
    label = registered_domain(host).split(".")[0] if host else url
    return label[:1].upper() + label[1:]


@router.post("", status_code=status.HTTP_201_CREATED)
def add_company(
    body: CompanyIn, session: SessionDep, user_id: UserDep, clients: ClientFactoryDep
) -> CompanyOut:
    """Careers page entered by the user (F7a); detected right away and watched."""
    url = body.url.strip()
    url = url if "://" in url else f"https://{url}"
    if not urlsplit(url).netloc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Ungültige URL")
    registry = CompanyRegistry(session, user_id)
    company = registry.get_or_create(body.name.strip() or _name_from_url(url), "user")
    if company is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Kein Firmenname erkennbar")
    company.careers_url = url
    if find_ats(url) is None and not company.website:
        parts = urlsplit(url)
        company.website = f"{parts.scheme}://{parts.netloc}"
    registry.link(company).status = "watch"
    _detect(session, user_id, company, clients)
    return _get(session, user_id, company.id)


def _detect(session: Session, user_id: int, company: Company, clients: ClientFactory) -> None:
    client = clients(load_settings(session, user_id))
    try:
        apply_detection(company, detect(client, company))
    finally:
        client.close()
    session.commit()


@router.patch("/{company_id}")
def update_company(
    company_id: int, body: CompanyPatch, session: SessionDep, user_id: UserDep
) -> CompanyOut:
    link = session.scalar(
        select(UserCompany).where(
            UserCompany.user_id == user_id, UserCompany.company_id == company_id
        )
    )
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Firma nicht gefunden")
    link.status = body.status
    session.commit()
    return _get(session, user_id, company_id)


@router.post("/{company_id}/detect")
def redetect(
    company_id: int, session: SessionDep, user_id: UserDep, clients: ClientFactoryDep
) -> CompanyOut:
    current = _get(session, user_id, company_id)
    company = session.get(Company, current.id)
    assert company is not None
    _detect(session, user_id, company, clients)
    return _get(session, user_id, company_id)
