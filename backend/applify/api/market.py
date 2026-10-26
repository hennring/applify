from datetime import date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from applify.db.session import get_session
from applify.services import market
from applify.services.skills import get_taxonomy
from applify.users import get_current_user_id

router = APIRouter(prefix="/market", tags=["market"])

SessionDep = Annotated[Session, Depends(get_session)]
UserDep = Annotated[int, Depends(get_current_user_id)]


class MarketStatus(BaseModel):
    last_seen_at: datetime | None
    extracted_at: datetime | None
    jobs_with_llm: int


class AnalysisStatus(BaseModel):
    # unknown: never recorded, pending: a newer search run waits for the pipeline.
    state: Literal["unknown", "running", "failed", "pending", "current"]
    started_at: datetime | None
    # End of the last successful run and the search run it covers.
    analyzed_at: datetime | None
    search_run_at: datetime | None
    latest_search_run_at: datetime | None


class RoleFamilyOption(BaseModel):
    key: str
    label: str


class MarketOptions(BaseModel):
    role_families: list[RoleFamilyOption]
    sources: list[str]


class MarketTotals(BaseModel):
    jobs: int
    full_text: int


class MarketCoverage(BaseModel):
    """Share of full-text jobs with each feature known (0..1)."""

    role_family: float
    seniority: float
    years: float
    salary: float


class SkillDemand(BaseModel):
    skill: str
    category: str
    jobs: int
    # Share of the full-text jobs in the selection.
    share: float
    # must / nice / avoid if the skill is in the profile.
    profile_weight: str | None


class SkillPair(BaseModel):
    skill_a: str
    skill_b: str
    jobs: int


class TrendSeries(BaseModel):
    skill: str
    shares: list[float]


class SkillTrend(BaseModel):
    weeks: list[date]
    series: list[TrendSeries]


class SeniorityMix(BaseModel):
    role_family: str
    label: str
    total: int
    counts: dict[str, int]


class YearsBucket(BaseModel):
    bucket: str
    jobs: int


class AgedJob(BaseModel):
    job_id: int
    title: str
    company: str
    location_raw: str
    role_label: str
    online_since: datetime
    age_days: int


class JobAge(BaseModel):
    # Open jobs only; age = days since publication (else first sighting).
    open: int
    median_days: int | None
    buckets: list[YearsBucket]
    oldest: list[AgedJob]
    newest: list[AgedJob]


class SalaryGroup(BaseModel):
    key: str
    label: str
    # Jobs in the group, and those stating a salary.
    total: int
    n: int
    p25: float
    median: float
    p75: float


class SkillCandidate(BaseModel):
    name: str
    jobs: int


class MarketOverview(BaseModel):
    # False until the analytics pipeline has built the marts once.
    available: bool
    analysis: AnalysisStatus
    status: MarketStatus | None = None
    options: MarketOptions | None = None
    totals: MarketTotals | None = None
    coverage: MarketCoverage | None = None
    skills: list[SkillDemand] = []
    gaps: list[SkillDemand] = []
    pairs: list[SkillPair] = []
    trend: SkillTrend | None = None
    seniority: list[SeniorityMix] = []
    years: list[YearsBucket] = []
    age: JobAge | None = None
    salary: list[SalaryGroup] = []
    candidates: list[SkillCandidate] = []
    categories: list[str] = []


class CandidateIn(BaseModel):
    name: str
    category: str


class CandidateAccepted(BaseModel):
    name: str
    jobs_rescanned: int


@router.get("")
def get_market(
    session: SessionDep,
    user_id: UserDep,
    scope: market.Scope = "all",
    role: str = "",
    seniority: str = "",
    source: str = "",
    weeks: Annotated[int, Query(ge=0, le=520)] = 0,
) -> MarketOverview:
    """Market dashboard (F23) for the selection; reads the marts of the pipeline (§5.8)."""
    analysis = market.analysis_status(session)
    if not market.marts_available(session):
        return MarketOverview(available=False, analysis=AnalysisStatus.model_validate(analysis))
    data = market.overview(
        session, user_id, market.MarketFilter(scope, role, seniority, source, weeks)
    )
    return MarketOverview.model_validate(
        {**data, "analysis": analysis, "categories": market.categories(get_taxonomy())}
    )


@router.post("/skill-candidates")
def accept_candidate(body: CandidateIn, session: SessionDep) -> CandidateAccepted:
    """Add a skill candidate to skills.yaml (also used by the matching from now on)."""
    try:
        touched = market.accept_candidate(session, body.name, body.category)
    except market.CandidateError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return CandidateAccepted(name=body.name.strip(), jobs_rescanned=touched)
