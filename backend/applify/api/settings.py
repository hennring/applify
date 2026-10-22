from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from applify.api.runs import SourceStats
from applify.config import get_settings
from applify.db.models import Company, JobSource, SearchRun, UserCompany
from applify.db.session import get_session
from applify.services.source_settings import (
    BY_KEY,
    CATALOG,
    GENERAL,
    load_settings,
    missing,
    save_setting,
)
from applify.users import get_current_user_id

router = APIRouter(prefix="/settings", tags=["settings"])

SessionDep = Annotated[Session, Depends(get_session)]
UserDep = Annotated[int, Depends(get_current_user_id)]


class SourceOut(BaseModel):
    key: str
    label: str
    kind: str
    description: str
    enabled: bool
    # Non-secret settings with their values; secrets only say whether they are set.
    fields: dict[str, str]
    secrets: dict[str, bool]
    missing: list[str]
    # Jobs in the stock delivered by this source; for discovery: companies found.
    count: int
    last_run: SourceStats | None


class SettingsOut(BaseModel):
    contact: str
    contact_from_env: bool
    sources: list[SourceOut]


class SourcePatch(BaseModel):
    enabled: bool | None = None
    # Value "" removes a setting; settings left out stay as they are.
    config: dict[str, str] = Field(default_factory=dict)


class GeneralPatch(BaseModel):
    contact: str = Field("", max_length=200)


def _counts(session: Session, user_id: int) -> dict[str, int]:
    counts: dict[str, int] = {}
    for source, n in session.execute(
        select(JobSource.source, func.count(func.distinct(JobSource.job_id))).group_by(
            JobSource.source
        )
    ):
        key = "careers" if source.startswith("ats:") or source == "jsonld" else source
        counts[key] = counts.get(key, 0) + n
    for origin, n in session.execute(
        select(Company.discovered_from, func.count())
        .join(UserCompany, UserCompany.company_id == Company.id)
        .where(UserCompany.user_id == user_id)
        .group_by(Company.discovered_from)
    ):
        counts[origin] = n
    return counts


def _last_run_stats(session: Session, user_id: int) -> dict[str, SourceStats]:
    run = session.scalar(
        select(SearchRun)
        .where(SearchRun.user_id == user_id, SearchRun.status != "running")
        .order_by(SearchRun.started_at.desc())
        .limit(1)
    )
    stats: dict[str, Any] = dict(run.stats) if run else {}
    merged: dict[str, dict[str, Any]] = {}
    for key, value in stats.items():
        target = "careers" if key.startswith("ats:") or key == "jsonld" else key
        into = merged.setdefault(target, {"label": value.get("label", key)})
        for name, n in value.items():
            if isinstance(n, int):
                into[name] = into.get(name, 0) + n
    return {k: SourceStats.model_validate(v) for k, v in merged.items() if "found" in v}


@router.get("/sources")
def get_sources(session: SessionDep, user_id: UserDep) -> SettingsOut:
    settings = load_settings(session, user_id)
    counts = _counts(session, user_id)
    last = _last_run_stats(session, user_id)
    contact = settings[GENERAL].config.get("contact") or ""
    return SettingsOut(
        contact=contact,
        contact_from_env=not contact and bool(get_settings().http_contact),
        sources=[
            SourceOut(
                key=info.key,
                label=info.label,
                kind=info.kind,
                description=info.description,
                enabled=settings[info.key].enabled,
                fields={
                    f: str(settings[info.key].config.get(f) or "")
                    for f in info.fields
                    if f not in info.secrets
                },
                secrets={f: bool(settings[info.key].config.get(f)) for f in info.secrets},
                missing=missing(info, settings[info.key]),
                count=counts.get(info.key, 0),
                last_run=last.get(info.key),
            )
            for info in CATALOG
        ],
    )


@router.put("/sources/{key}")
def update_source(
    key: str, body: SourcePatch, session: SessionDep, user_id: UserDep
) -> SettingsOut:
    info = BY_KEY.get(key)
    if info is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unbekannte Quelle")
    unknown = set(body.config) - set(info.fields)
    if unknown:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"Unbekannte Felder: {sorted(unknown)}"
        )
    config = {name: value.strip() or None for name, value in body.config.items()}
    save_setting(session, user_id, key, enabled=body.enabled, **config)
    session.commit()
    return get_sources(session, user_id)


@router.put("/general")
def update_general(body: GeneralPatch, session: SessionDep, user_id: UserDep) -> SettingsOut:
    save_setting(session, user_id, GENERAL, contact=body.contact.strip() or None)
    session.commit()
    return get_sources(session, user_id)
