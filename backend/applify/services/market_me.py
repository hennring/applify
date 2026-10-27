"""Tab "Ich & Markt" (§5.9, D24): the market seen from the user's profile.

Computed live from the current profile: the jobs of the selection are rated in memory, and
for the skills the profile lacks, the skill component is rated again as if the skill were in
the profile. Nothing is stored.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from statistics import mean
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from applify.db.models import Job, JobMatch
from applify.schemas.profile import ProfileData, Skill
from applify.services.geo import get_gazetteer
from applify.services.market import MarketFilter, query_rows, selection_where
from applify.services.match_store import Scorer, facts
from applify.services.matching import (
    SKILL_TARGET,
    Component,
    JobFacts,
    hard_filter,
    score_components,
    score_skills,
    total_score,
)
from applify.services.skills import get_taxonomy, match_key

# Same bound as the "high" score badge in the job list.
GOOD_SCORE = 75
LEVER_SKILLS = 30
SCORE_BUCKETS = (("0–24", 0, 24), ("25–49", 25, 49), ("50–74", 50, 74), ("75–100", 75, 100))


@dataclass
class Rated:
    facts: JobFacts
    components: list[Component]
    score: int
    week: date


def _skill_target(profile: ProfileData) -> float:
    wanted = [s for s in profile.skills if s.weight in ("must", "nice")]
    return min(SKILL_TARGET, sum(1.0 if s.weight == "must" else 0.5 for s in wanted))


def me(session: Session, user_id: int, f: MarketFilter) -> dict[str, Any]:
    where, params = selection_where(f, user_id)
    selection = {
        r.job_id: r
        for r in query_rows(
            session,
            f"""select f.job_id, f.first_seen_week, f.years_min, f.salary_min_eur,
                f.salary_max_eur from marts.fct_job_postings f where {where}""",
            params,
        )
    }
    scorer = Scorer(session, user_id, get_gazetteer(), get_taxonomy())
    jobs = session.scalars(select(Job).where(Job.id.in_(selection))).all()
    # The hard filters are slow (language patterns over the whole text); their result is
    # stored with each match and renewed whenever the profile changes.
    stored = dict(
        session.execute(
            select(JobMatch.job_id, JobMatch.excluded_reason).where(
                JobMatch.user_id == user_id, JobMatch.job_id.in_(selection)
            )
        ).all()
    )
    rated: list[Rated] = []
    excluded = 0
    for job in jobs:
        job_facts = facts(job, scorer.taxonomy)
        profile, places, taxonomy = scorer.profile, scorer.places, scorer.taxonomy
        reason = (
            stored[job.id]
            if job.id in stored
            else hard_filter(job_facts, profile, places, taxonomy)
        )
        if reason:
            excluded += 1
            continue
        components = score_components(job_facts, profile, places, taxonomy)
        week = selection[job.id].first_seen_week
        rated.append(Rated(job_facts, components, total_score(components), week))
    profile = scorer.profile
    return {
        "good_score": GOOD_SCORE,
        "jobs": len(rated),
        "excluded": excluded,
        "good": sum(r.score >= GOOD_SCORE for r in rated),
        "scores": [
            {"bucket": label, "jobs": sum(low <= r.score <= high for r in rated)}
            for label, low, high in SCORE_BUCKETS
        ],
        "weekly": _weekly(rated),
        "lever": skill_lever(rated, profile, scorer.taxonomy),
        "fit": _fit(profile, list(selection.values())),
    }


def skill_lever(rated: list[Rated], profile: ProfileData, taxonomy: Any) -> list[dict[str, Any]]:
    """For the most asked skills outside the profile: jobs that would become good matches."""
    own = {match_key(s.name) for s in profile.skills}
    asked = Counter(
        name for r in rated for name in set(r.facts.skills) if match_key(name) not in own
    )
    target = _skill_target(profile)
    lever: list[dict[str, Any]] = []
    for name, jobs in asked.most_common(LEVER_SKILLS):
        known = taxonomy.lookup(name)
        skill = Skill(
            name=name, canonical=known is not None, category=known.category if known else None
        )
        added = profile.model_copy(update={"skills": [*profile.skills, skill]})
        # A new skill can raise the target number of hits and so lower other jobs' scores.
        everywhere = _skill_target(added) != target
        gained = lost = 0
        gains = []
        for r in rated:
            has_skill = name in r.facts.skills
            if not (has_skill or everywhere):
                continue
            others = [c for c in r.components if c.key != "skills"]
            score = total_score([score_skills(r.facts, added, taxonomy), *others])
            if has_skill:
                gains.append(score - r.score)
            gained += r.score < GOOD_SCORE <= score
            lost += score < GOOD_SCORE <= r.score
        lever.append(
            {
                "skill": name,
                "category": known.category if known else None,
                "jobs": jobs,
                "new_good": gained - lost,
                "avg_gain": mean(gains) if gains else 0.0,
            }
        )
    lever.sort(key=lambda s: (-s["new_good"], -s["avg_gain"], s["skill"]))
    return lever


def _weekly(rated: list[Rated]) -> list[dict[str, Any]]:
    weeks: dict[date, list[int]] = defaultdict(lambda: [0, 0])
    for r in rated:
        weeks[r.week][0] += 1
        weeks[r.week][1] += r.score >= GOOD_SCORE
    return [{"week": w, "jobs": n, "good": good} for w, (n, good) in sorted(weeks.items())]


def _fit(profile: ProfileData, selection: list[Any]) -> dict[str, Any]:
    """How the asked experience and the offered salaries compare to the profile."""
    years = [r.years_min for r in selection if r.years_min is not None]
    salaries = [
        r.salary_max_eur if r.salary_max_eur is not None else r.salary_min_eur
        for r in selection
        if r.salary_min_eur is not None or r.salary_max_eur is not None
    ]
    own_years, own_salary = profile.seniority_years, profile.salary_min
    return {
        "years": own_years,
        "years_known": len(years),
        "years_fit": None if own_years is None else sum(y <= own_years for y in years),
        "salary_min": own_salary,
        "salary_known": len(salaries),
        "salary_fit": None if own_salary is None else sum(s >= own_salary for s in salaries),
    }
