from datetime import date, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from applify.db.session import get_session
from applify.services import (
    market,
    market_dynamics,
    market_employers,
    market_me,
    market_regions,
)
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


class StackAge(BaseModel):
    skills: list[str]
    open: int
    mean_days: int | None
    median_days: int | None


class RoleAge(BaseModel):
    role_family: str
    label: str
    open: int
    mean_days: int | None
    median_days: int | None
    # Stacks with enough open jobs, highest median age first.
    stacks: list[StackAge]


class JobAge(BaseModel):
    # Open jobs only; age = days since publication (else first sighting).
    open: int
    mean_days: int | None
    median_days: int | None
    buckets: list[YearsBucket]
    # Role families with enough open jobs, highest median age first.
    roles: list[RoleAge]


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


class BenefitShare(BaseModel):
    benefit: str
    jobs: int
    # Of the full-text jobs in the selection.
    share: float


class BenefitRole(BaseModel):
    role_family: str
    label: str
    jobs: int
    # Benefit → share of the role family's full-text jobs.
    shares: dict[str, float]


class VacationDays(BaseModel):
    known: int
    median: int | None
    buckets: list[YearsBucket]


class StackShare(BaseModel):
    skills: list[str]
    jobs: int
    roles: list[str]


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
    benefits: list[BenefitShare] = []
    benefit_roles: list[BenefitRole] = []
    vacation: VacationDays | None = None
    stacks: list[StackShare] = []
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


class SkillLever(BaseModel):
    skill: str
    category: str | None
    # Jobs of the selection asking for the skill.
    jobs: int
    # Jobs that would become good matches with the skill in the profile (net).
    new_good: int
    avg_gain: float


class ScoreBucket(BaseModel):
    bucket: str
    jobs: int


class WeeklyMatches(BaseModel):
    week: date
    jobs: int
    good: int


class ProfileFit(BaseModel):
    years: float | None
    years_known: int
    years_fit: int | None
    salary_min: int | None
    salary_known: int
    salary_fit: int | None


class MarketMe(BaseModel):
    good_score: int
    jobs: int
    excluded: int
    good: int
    scores: list[ScoreBucket]
    weekly: list[WeeklyMatches]
    lever: list[SkillLever]
    fit: ProfileFit


class Employer(BaseModel):
    company_norm: str
    company: str
    jobs: int
    active: int
    agency: bool
    # Most frequent role families of the company's jobs.
    roles: list[str]


class AgencyEmployer(BaseModel):
    company: str
    jobs: int


class RepeatedTitle(BaseModel):
    company: str
    title: str
    jobs: int
    # Distinct places the title is posted for.
    places: int
    # Times it reappeared after all earlier postings had vanished for a week.
    reposts: int
    first_seen_at: datetime
    last_seen_at: datetime


class MarketEmployers(BaseModel):
    jobs: int
    companies: int
    # Share of the selection posted by the ten largest employers.
    top10_share: float
    top: list[Employer]
    agencies: list[AgencyEmployer]
    repeated: list[RepeatedTitle]


class StateJobs(BaseModel):
    state_code: str
    state_name: str
    population: int
    jobs: int
    remote: int
    per_100k: float


class CityJobs(BaseModel):
    city: str
    state_code: str
    jobs: int


class DistanceBucket(BaseModel):
    bucket: str
    jobs: int


class MarketRegions(BaseModel):
    states: list[StateJobs]
    # Jobs without a state: abroad, place unknown, fully remote without a place.
    abroad: int
    unknown: int
    remote_without_place: int
    cities: list[CityJobs]
    # Distance to the nearest place of the profile.
    distances: list[DistanceBucket]


class WeeklyFlow(BaseModel):
    week: date
    # Postings first seen in the week, and postings last seen in it that have vanished.
    new: int
    gone: int


class LifespanGroup(BaseModel):
    label: str
    closed: int
    median_days: float


class Lifespan(BaseModel):
    open: int
    closed: int
    min_closed: int
    median_days: float | None
    by_role: list[LifespanGroup]
    by_skill: list[LifespanGroup]


class SkillChange(BaseModel):
    skill: str
    recent_share: float
    previous_share: float
    delta: float


class SkillChanges(BaseModel):
    # False while one of the two windows has too few jobs.
    ready: bool
    recent_from: date | None
    previous_from: date | None
    recent_jobs: int
    previous_jobs: int
    min_window_jobs: int
    rising: list[SkillChange]
    falling: list[SkillChange]


class MarketDynamics(BaseModel):
    history_start: date | None
    history_days: int
    trend_ready_on: date | None
    flow: list[WeeklyFlow]
    lifespan: Lifespan
    skills: SkillChanges


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


@router.get("/me")
def get_market_me(session: SessionDep, user_id: UserDep, f: FilterDep) -> MarketMe | None:
    """Tab "Ich & Markt" (§5.9, D24): fit of the profile and the skills with most leverage."""
    if not market.marts_available(session):
        return None
    return MarketMe.model_validate(market_me.me(session, user_id, f))


@router.get("/employers")
def get_market_employers(
    session: SessionDep, user_id: UserDep, f: FilterDep
) -> MarketEmployers | None:
    """Tab "Arbeitgeber" (§5.9): largest employers, repeated titles, staffing agencies."""
    if not market.marts_available(session):
        return None
    return MarketEmployers.model_validate(market_employers.employers(session, user_id, f))


@router.get("/regions")
def get_market_regions(session: SessionDep, user_id: UserDep, f: FilterDep) -> MarketRegions | None:
    """Tab "Regionen" (§5.9): jobs per state and city, distance to the profile's places."""
    if not market.marts_available(session):
        return None
    return MarketRegions.model_validate(market_regions.regions(session, user_id, f))


@router.get("/dynamics")
def get_market_dynamics(
    session: SessionDep, user_id: UserDep, f: FilterDep
) -> MarketDynamics | None:
    """Tab "Dynamik" (§5.9): flow of postings, lifespans, rising and falling skills."""
    if not market.marts_available(session):
        return None
    return MarketDynamics.model_validate(market_dynamics.dynamics(session, user_id, f))


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
