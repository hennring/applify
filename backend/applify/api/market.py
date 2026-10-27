from datetime import date, datetime
from typing import Annotated, Any, Literal

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
    # Jobs of staffing agencies and recruiters in the selection.
    agencies: int


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


class SourceValue(BaseModel):
    source: str
    source_group: str
    jobs: int
    # Jobs no other source delivered.
    only_here: int
    full_text: int
    active: int


class CoveragePoint(BaseModel):
    recorded_at: datetime
    jobs: int
    full_text: int
    # Feature → share of full-text jobs with it determined.
    coverage: dict[str, float]
    llm_processed: int
    llm_failed: int
    llm_queue: int


class CheckResult(BaseModel):
    check_name: str
    passed: bool
    detail: dict[str, Any]
    checked_at: datetime


class PipelineRun(BaseModel):
    status: str
    started_at: datetime
    finished_at: datetime | None
    search_run_at: datetime | None


class MarketData(BaseModel):
    sources: list[SourceValue]
    history: list[CoveragePoint]
    checks: list[CheckResult]
    runs: list[PipelineRun]


class CandidateIn(BaseModel):
    name: str
    category: str


class CandidateAccepted(BaseModel):
    name: str
    jobs_rescanned: int


def market_filter(
    scope: market.Scope = "all",
    role: str = "",
    seniority: str = "",
    source: str = "",
    weeks: Annotated[int, Query(ge=0, le=520)] = 0,
    agencies: bool = True,
) -> market.MarketFilter:
    """Filters shared by all tabs of the market dashboard."""
    return market.MarketFilter(scope, role, seniority, source, weeks, agencies)


FilterDep = Annotated[market.MarketFilter, Depends(market_filter)]


@router.get("")
def get_market(session: SessionDep, user_id: UserDep, f: FilterDep) -> MarketOverview:
    """Market dashboard (F23) for the selection; reads the marts of the pipeline (§5.8)."""
    analysis = market.analysis_status(session)
    if not market.marts_available(session):
        return MarketOverview(available=False, analysis=AnalysisStatus.model_validate(analysis))
    data = market.overview(session, user_id, f)
    return MarketOverview.model_validate(
        {**data, "analysis": analysis, "categories": market.categories(get_taxonomy())}
    )


@router.get("/data")
def get_market_data(session: SessionDep) -> MarketData:
    """Tab "Daten" (§5.9): value of each source and data quality; independent of the filters."""
    if not market.marts_available(session):
        return MarketData(sources=[], history=[], checks=[], runs=[])
    return MarketData.model_validate(market.data_quality(session))


@router.post("/skill-candidates")
def accept_candidate(body: CandidateIn, session: SessionDep) -> CandidateAccepted:
    """Add a skill candidate to skills.yaml (also used by the matching from now on)."""
    try:
        touched = market.accept_candidate(session, body.name, body.category)
    except market.CandidateError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return CandidateAccepted(name=body.name.strip(), jobs_rescanned=touched)
