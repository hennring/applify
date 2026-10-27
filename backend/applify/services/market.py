"""Market dashboard (F23): reads the marts built by the analytics pipeline (§5.8).

The marts are owned by dbt; until the pipeline has run once they do not exist, and the
dashboard says so instead of failing.
"""

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Literal, cast

from sqlalchemy import CursorResult, select, text, update
from sqlalchemy.orm import Session

from applify.db.models import Job, Profile, ProfileSkill, SearchRun
from applify.services.match_store import rescore_user
from applify.services.skills import SKILLS_FILE, SkillTaxonomy, get_taxonomy

Scope = Literal["area", "germany", "all"]

YEAR_BUCKETS = (("0–1", 0, 1), ("2", 2, 2), ("3–4", 3, 4), ("5–6", 5, 6), ("7+", 7, 99))
# Days online of open jobs.
AGE_BUCKETS = (
    ("< 1 Woche", 0, 6),
    ("1–2 Wochen", 7, 13),
    ("2–4 Wochen", 14, 29),
    ("1–2 Monate", 30, 59),
    ("2–3 Monate", 60, 89),
    ("3–6 Monate", 90, 179),
    ("6–12 Monate", 180, 364),
    ("> 1 Jahr", 365, 1_000_000),
)
AGE_LIST_LIMIT = 15
SENIORITY_ORDER = ("student", "junior", "mid", "senior", "lead", "unknown")


@dataclass(frozen=True)
class MarketFilter:
    scope: Scope = "all"
    # "" all, "mine" the families of the profile's desired roles, or a family key.
    role: str = ""
    seniority: str = ""
    source: str = ""
    # Jobs first seen within the last N weeks; 0 = all.
    weeks: int = 0
    # False hides jobs posted by staffing agencies and recruiters (D25).
    agencies: bool = True


def marts_available(session: Session) -> bool:
    return bool(session.scalar(text("select to_regclass('marts.fct_job_postings') is not null")))


AnalysisState = Literal["unknown", "running", "failed", "pending", "current"]


def analysis_status(session: Session) -> dict[str, Any]:
    """Whether the marts cover the newest search run; the pipeline records its runs."""
    latest_search = session.execute(
        select(SearchRun.id, SearchRun.finished_at)
        .where(SearchRun.status != "running")
        .order_by(SearchRun.id.desc())
        .limit(1)
    ).first()
    status: dict[str, Any] = {
        "state": "unknown",
        "started_at": None,
        "analyzed_at": None,
        "search_run_at": None,
        "latest_search_run_at": latest_search.finished_at if latest_search else None,
    }
    if not session.scalar(text("select to_regclass('features.pipeline_runs') is not null")):
        return status
    runs = _rows(
        session,
        """select status, started_at, finished_at, search_run_id
        from features.pipeline_runs order by started_at desc limit 20""",
        {},
    )
    if not runs:
        return status
    status["started_at"] = runs[0].started_at
    success = next((r for r in runs if r.status == "success"), None)
    if success is not None:
        status["analyzed_at"] = success.finished_at
        status["search_run_at"] = session.scalar(
            select(SearchRun.finished_at).where(SearchRun.id == success.search_run_id)
        )
    covered = success.search_run_id if success is not None else None
    state: AnalysisState
    if runs[0].status == "running":
        state = "running"
    elif runs[0].status in ("failed", "canceled"):
        state = "failed"
    elif latest_search is not None and (covered is None or latest_search.id > covered):
        state = "pending"
    else:
        state = "current"
    status["state"] = state
    return status


def _where(f: MarketFilter, user_id: int) -> tuple[str, dict[str, Any]]:
    clauses = ["true"]
    params: dict[str, Any] = {"user_id": user_id}
    if f.weeks:
        clauses.append("f.first_seen_at >= now() - make_interval(weeks => :weeks)")
        params["weeks"] = f.weeks
    if f.scope == "germany":
        clauses.append("f.scope = 'germany'")
    elif f.scope == "area":
        # Within a radius of the profile's places, or fully remote in Germany.
        clauses.append(
            "(exists (select 1 from marts.fct_job_profile_area a "
            "where a.job_id = f.job_id and a.user_id = :user_id) "
            "or (f.remote_type = 'remote' and f.scope = 'germany'))"
        )
    if f.role == "mine":
        clauses.append(
            "f.role_family in (select role_family from features.profile_role_families "
            "where user_id = :user_id)"
        )
    elif f.role:
        clauses.append("f.role_family = :role")
        params["role"] = f.role
    if f.seniority:
        clauses.append("f.seniority = :seniority")
        params["seniority"] = f.seniority
    if f.source:
        clauses.append(":source = any(f.source_groups)")
        params["source"] = f.source
    if not f.agencies:
        clauses.append("not f.is_agency")
    return " and ".join(clauses), params


def _rows(session: Session, sql: str, params: dict[str, Any]) -> list[Any]:
    return list(session.execute(text(sql), params))


def profile_skills(session: Session, user_id: int) -> dict[str, str]:
    """Lower-cased skill name → weight (must / nice / avoid)."""
    rows = session.execute(
        select(ProfileSkill.skill, ProfileSkill.weight)
        .join(Profile, Profile.id == ProfileSkill.profile_id)
        .where(Profile.user_id == user_id)
    )
    return {skill.casefold(): weight for skill, weight in rows}


def overview(session: Session, user_id: int, f: MarketFilter) -> dict[str, Any]:
    where, params = _where(f, user_id)
    jobs = f"select * from marts.fct_job_postings f where {where}"
    full = f"select * from marts.fct_job_postings f where {where} and f.has_full_text"

    total, full_text, agencies = _rows(
        session,
        f"""select count(*), count(*) filter (where has_full_text),
            count(*) filter (where is_agency) from ({jobs}) j""",
        params,
    )[0]
    coverage = _rows(
        session,
        f"""select
            avg((role_family <> 'unknown')::int), avg((seniority <> 'unknown')::int),
            avg((years_min is not null)::int), avg((salary_mid_eur is not null)::int)
        from ({full}) j""",
        params,
    )[0]

    own = profile_skills(session, user_id)
    demand = _rows(
        session,
        f"""select b.skill, b.category, count(*) as jobs
        from ({full}) j join marts.bridge_job_skills b using (job_id)
        group by b.skill, b.category order by jobs desc, b.skill limit 200""",
        params,
    )

    def skill_row(r: Any) -> dict[str, Any]:
        weight = own.get(r.skill.casefold())
        return {
            "skill": r.skill,
            "category": r.category,
            "jobs": r.jobs,
            "share": r.jobs / full_text if full_text else 0.0,
            "profile_weight": weight,
        }

    skills = [skill_row(r) for r in demand[:25]]
    gaps = [skill_row(r) for r in demand if own.get(r.skill.casefold()) is None][:15]

    pairs = _rows(
        session,
        f"""select a.skill as skill_a, b.skill as skill_b, count(*) as jobs
        from ({full}) j
        join marts.bridge_job_skills a using (job_id)
        join marts.bridge_job_skills b on b.job_id = a.job_id and a.skill < b.skill
        group by a.skill, b.skill having count(*) >= 2
        order by jobs desc, a.skill, b.skill limit 12""",
        params,
    )

    return {
        "available": True,
        "status": _status(session),
        "options": _options(session),
        "totals": {"jobs": total, "full_text": full_text, "agencies": agencies},
        "coverage": {
            "role_family": float(coverage[0] or 0),
            "seniority": float(coverage[1] or 0),
            "years": float(coverage[2] or 0),
            "salary": float(coverage[3] or 0),
        },
        "skills": skills,
        "gaps": gaps,
        "pairs": [dict(r._mapping) for r in pairs],
        "trend": _trend(session, full, params, [s["skill"] for s in skills[:5]]),
        "seniority": _seniority(session, full, params),
        "years": _years(session, full, params),
        "age": _age(session, jobs, params),
        "salary": _salary(session, full, params, by_seniority=f.role not in ("", "mine")),
        "candidates": _candidates(session, full, params, get_taxonomy()),
    }


def _status(session: Session) -> dict[str, Any]:
    row = _rows(
        session,
        """select
            (select max(last_seen_at) from marts.fct_job_postings) as last_seen_at,
            (select max(extracted_at) from features.job_features) as extracted_at,
            (select count(*) from features.job_features where origin::text like '%llm%')
                as jobs_with_llm""",
        {},
    )[0]
    return dict(row._mapping)


def _options(session: Session) -> dict[str, Any]:
    families = _rows(
        session, "select role_family, label from marts.dim_role_family order by sort_order", {}
    )
    sources = _rows(
        session,
        "select distinct unnest(source_groups) as source from marts.fct_job_postings order by 1",
        {},
    )
    return {
        "role_families": [{"key": r.role_family, "label": r.label} for r in families],
        "sources": [r.source for r in sources],
    }


def _trend(
    session: Session, full: str, params: dict[str, Any], skills: list[str]
) -> dict[str, Any]:
    """Weekly share of jobs naming each of the top skills."""
    weeks: list[date] = [
        r.week
        for r in _rows(
            session, f"select distinct first_seen_week as week from ({full}) j order by 1", params
        )
    ]
    if not skills:
        return {"weeks": weeks, "series": []}
    rows = _rows(
        session,
        f"""with j as ({full}),
        totals as (select first_seen_week, count(*) as n from j group by 1)
        select j.first_seen_week as week, b.skill, count(*)::float / t.n as share
        from j join marts.bridge_job_skills b using (job_id)
        join totals t using (first_seen_week)
        where b.skill = any(:skills)
        group by j.first_seen_week, b.skill, t.n""",
        {**params, "skills": skills},
    )
    shares = {(r.week, r.skill): r.share for r in rows}
    return {
        "weeks": weeks,
        "series": [
            {"skill": skill, "shares": [shares.get((week, skill), 0.0) for week in weeks]}
            for skill in skills
        ],
    }


def _seniority(session: Session, full: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    rows = _rows(
        session,
        f"""select j.role_family, coalesce(d.label, 'Unbekannt') as label,
            coalesce(d.sort_order, 999) as sort_order, j.seniority, count(*) as jobs
        from ({full}) j left join marts.dim_role_family d using (role_family)
        group by 1, 2, 3, 4""",
        params,
    )
    families: dict[str, dict[str, Any]] = {}
    for r in sorted(rows, key=lambda r: r.sort_order):
        family = families.setdefault(
            r.role_family,
            {"role_family": r.role_family, "label": r.label, "total": 0, "counts": {}},
        )
        family["counts"][r.seniority] = r.jobs
        family["total"] += r.jobs
    return sorted(families.values(), key=lambda f: -f["total"])


def _years(session: Session, full: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    rows = _rows(session, f"select years_min from ({full}) j where years_min is not null", params)
    return [
        {"bucket": label, "jobs": sum(1 for r in rows if low <= r.years_min <= high)}
        for label, low, high in YEAR_BUCKETS
    ]


def _age(session: Session, jobs: str, params: dict[str, Any]) -> dict[str, Any]:
    """How long the open jobs have been online: distribution, median, oldest and newest."""
    rows = _rows(session, f"select age_days from ({jobs}) j where is_active", params)
    ages = sorted(r.age_days for r in rows)

    def listed(order: str) -> list[dict[str, Any]]:
        return [
            dict(r._mapping)
            for r in _rows(
                session,
                f"""select j.job_id, j.title, j.company, j.location_raw, j.online_since,
                    j.age_days, coalesce(d.label, 'Unbekannt') as role_label
                from ({jobs}) j left join marts.dim_role_family d using (role_family)
                where j.is_active order by j.age_days {order}, j.job_id limit {AGE_LIST_LIMIT}""",
                params,
            )
        ]

    return {
        "open": len(ages),
        "median_days": ages[len(ages) // 2] if ages else None,
        "buckets": [
            {"bucket": label, "jobs": sum(1 for a in ages if low <= a <= high)}
            for label, low, high in AGE_BUCKETS
        ],
        "oldest": listed("desc"),
        "newest": listed("asc"),
    }


def _salary(
    session: Session, full: str, params: dict[str, Any], *, by_seniority: bool
) -> list[dict[str, Any]]:
    """Quartiles of the yearly gross salary (EUR) per group, with n of all jobs in it."""
    if by_seniority:
        group, label = "j.seniority", "j.seniority"
        join = ""
    else:
        group, label = "j.role_family", "coalesce(d.label, 'Unbekannt')"
        join = "left join marts.dim_role_family d using (role_family)"
    rows = _rows(
        session,
        f"""select {group} as key, {label} as label, count(*) as total,
            count(salary_mid_eur) as n,
            percentile_cont(0.25) within group (order by salary_mid_eur) as p25,
            percentile_cont(0.5) within group (order by salary_mid_eur) as median,
            percentile_cont(0.75) within group (order by salary_mid_eur) as p75
        from ({full}) j {join}
        group by 1, 2 having count(salary_mid_eur) > 0
        order by n desc, 1""",
        params,
    )
    result = [dict(r._mapping) for r in rows]
    if by_seniority:
        result.sort(key=lambda r: SENIORITY_ORDER.index(r["key"]))
    return result


def _candidates(
    session: Session, full: str, params: dict[str, Any], taxonomy: SkillTaxonomy
) -> list[dict[str, Any]]:
    rows = _rows(
        session,
        f"""select c.candidate as name, count(*) as jobs
        from ({full}) j join marts.bridge_job_skill_candidates c using (job_id)
        group by c.candidate order by jobs desc, c.candidate limit 40""",
        params,
    )
    # Accepted since the last pipeline run: already in the taxonomy.
    return [dict(r._mapping) for r in rows if taxonomy.lookup(r.name) is None][:20]


# --- skill candidates → taxonomy ----------------------------------------------------------

NAME = re.compile(r"^[\w.+#/ -]{2,40}$")


class CandidateError(ValueError):
    """A candidate cannot be added to the taxonomy."""


def categories(taxonomy: SkillTaxonomy) -> list[str]:
    return sorted({skill.category for skill in taxonomy.skills})


def accept_candidate(
    session: Session, name: str, category: str, *, skills_file: Path = SKILLS_FILE
) -> int:
    """Add a skill to skills.yaml; jobs naming it are rated again. Returns the jobs touched.

    The analytics pipeline picks the change up through the taxonomy's content hash.
    """
    name = name.strip()
    taxonomy = get_taxonomy()
    if not NAME.match(name):
        raise CandidateError("Ungültiger Name")
    if taxonomy.lookup(name) is not None:
        raise CandidateError(f"{name} ist schon in der Taxonomie")
    if category not in categories(taxonomy):
        raise CandidateError(f"Unbekannte Kategorie: {category}")
    entry = f"- {{name: {json.dumps(name, ensure_ascii=False)}, category: {category}}}\n"
    content = skills_file.read_text(encoding="utf-8")
    marker = "# --- Added from the market analysis ---"
    if marker not in content:
        content = content.rstrip("\n") + f"\n\n{marker}\n"
    skills_file.write_text(content + entry, encoding="utf-8")
    get_taxonomy.cache_clear()

    # Skills of jobs are scanned once per text; scan those naming the new skill again.
    pattern = re.escape(name)
    result = session.execute(
        update(Job)
        .where(Job.description.op("~*")(rf"(^|[^\w]){pattern}([^\w]|$)"))
        .values(skills=None)
    )
    touched = cast(CursorResult[Any], result).rowcount
    for user_id in session.scalars(select(Profile.user_id)):
        rescore_user(session, user_id)
    session.commit()
    return touched


# --- tab "Daten": sources and data quality (§5.9) ----------------------------------------

HISTORY_LIMIT = 60
RUN_LIMIT = 10


def _table_exists(session: Session, name: str) -> bool:
    return bool(session.scalar(text("select to_regclass(:name) is not null"), {"name": name}))


def data_quality(session: Session) -> dict[str, Any]:
    """What each source contributes and how complete the features are over time."""
    sources = _rows(
        session,
        """select source, source_group, jobs, only_here, full_text, active
        from marts.agg_source_value order by jobs desc, source""",
        {},
    )
    history: list[Any] = []
    if _table_exists(session, "features.coverage_history"):
        history = _rows(
            session,
            f"""select * from (
                select recorded_at, jobs, full_text, coverage, llm_processed, llm_failed, llm_queue
                from features.coverage_history order by recorded_at desc limit {HISTORY_LIMIT}
            ) h order by recorded_at""",
            {},
        )
    checks: list[Any] = []
    if _table_exists(session, "features.check_results"):
        checks = _rows(
            session,
            """select distinct on (check_name) check_name, passed, detail, checked_at
            from features.check_results order by check_name, checked_at desc""",
            {},
        )
    runs: list[Any] = []
    if _table_exists(session, "features.pipeline_runs"):
        runs = _rows(
            session,
            f"""select p.status, p.started_at, p.finished_at, s.finished_at as search_run_at
            from features.pipeline_runs p left join search_runs s on s.id = p.search_run_id
            order by p.started_at desc limit {RUN_LIMIT}""",
            {},
        )
    return {
        "sources": [dict(r._mapping) for r in sources],
        "history": [dict(r._mapping) for r in history],
        "checks": [dict(r._mapping) for r in checks],
        "runs": [dict(r._mapping) for r in runs],
    }
