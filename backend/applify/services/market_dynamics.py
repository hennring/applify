"""Tab "Dynamik" (§5.9): how the market moves over time.

Everything here needs history: lifespans need postings that have vanished, trends need two
full comparison windows. Until there is enough, the tab says from when on it will be.
"""

from datetime import date, timedelta
from statistics import median
from typing import Any

from sqlalchemy.orm import Session

from applify.services.market import MarketFilter, query_rows, selection_where

# Compared windows for rising and falling skills, in weeks.
WINDOW_WEEKS = 4
# Minimum jobs with full text per window, and per skill in one of the windows.
MIN_WINDOW_JOBS = 30
MIN_SKILL_JOBS = 5
# Minimum vanished postings for a median lifespan.
MIN_CLOSED = 10
TOP_CHANGES = 10
LIFESPAN_SKILLS = 15


def dynamics(session: Session, user_id: int, f: MarketFilter) -> dict[str, Any]:
    where, params = selection_where(f, user_id)
    jobs = f"select * from marts.fct_job_postings f where {where}"
    first, latest = query_rows(
        session,
        "select min(seen_at)::date, max(seen_at)::date from raw.job_sightings",
        {},
    )[0]
    return {
        "history_start": first,
        "history_days": (latest - first).days if first and latest else 0,
        # Two full windows of sightings make the comparison meaningful.
        "trend_ready_on": first + timedelta(weeks=2 * WINDOW_WEEKS) if first else None,
        "flow": _flow(session, jobs, params),
        "lifespan": _lifespan(session, jobs, params),
        "skills": _skill_change(session, jobs, params),
    }


def _flow(session: Session, jobs: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    """New postings per week and postings that vanished in that week."""
    rows = query_rows(
        session,
        f"""select week, sum(new)::int as new, sum(gone)::int as gone from (
            select first_seen_week as week, 1 as new, 0 as gone from ({jobs}) j
            union all
            select date_trunc('week', last_seen_at)::date, 0, 1 from ({jobs}) j
            where not is_active
        ) w group by week order by week""",
        params,
    )
    return [dict(r._mapping) for r in rows]


def _lifespan(session: Session, jobs: str, params: dict[str, Any]) -> dict[str, Any]:
    """Days vanished postings were online, overall, per role family and per skill."""
    closed = query_rows(
        session,
        f"""select j.job_id, j.age_days, coalesce(d.label, 'Unbekannt') as role
        from ({jobs}) j left join marts.dim_role_family d using (role_family)
        where not j.is_active""",
        params,
    )
    skills = query_rows(
        session,
        f"""select b.skill, j.age_days from ({jobs}) j
        join marts.bridge_job_skills b using (job_id) where not j.is_active""",
        params,
    )
    open_jobs = query_rows(session, f"select count(*) from ({jobs}) j where j.is_active", params)[
        0
    ][0]

    def grouped(pairs: list[tuple[str, int]], limit: int) -> list[dict[str, Any]]:
        groups: dict[str, list[int]] = {}
        for key, days in pairs:
            groups.setdefault(key, []).append(days)
        enough = sorted(
            ((key, days) for key, days in groups.items() if len(days) >= MIN_CLOSED),
            key=lambda group: (-len(group[1]), group[0]),
        )
        return [
            {"label": key, "closed": len(days), "median_days": median(days)}
            for key, days in enough[:limit]
        ]

    days = [r.age_days for r in closed]
    return {
        "open": open_jobs,
        "closed": len(days),
        "min_closed": MIN_CLOSED,
        "median_days": median(days) if len(days) >= MIN_CLOSED else None,
        "by_role": grouped([(r.role, r.age_days) for r in closed], 10),
        "by_skill": grouped([(r.skill, r.age_days) for r in skills], LIFESPAN_SKILLS),
    }


def _skill_change(session: Session, jobs: str, params: dict[str, Any]) -> dict[str, Any]:
    """Share of full-text jobs asking for each skill: the last WINDOW_WEEKS weeks against the
    WINDOW_WEEKS before."""
    latest = query_rows(session, f"select max(first_seen_week) from ({jobs}) j", params)[0][0]
    if latest is None:
        return _no_change(0, 0)
    recent_from = latest - timedelta(weeks=WINDOW_WEEKS - 1)
    previous_from = recent_from - timedelta(weeks=WINDOW_WEEKS)
    window = {**params, "recent": recent_from, "previous": previous_from}
    totals = query_rows(
        session,
        f"""select count(*) filter (where first_seen_week >= :recent),
            count(*) filter (where first_seen_week >= :previous and first_seen_week < :recent)
        from ({jobs}) j where has_full_text""",
        window,
    )[0]
    recent_jobs, previous_jobs = totals
    if min(recent_jobs, previous_jobs) < MIN_WINDOW_JOBS:
        return _no_change(recent_jobs, previous_jobs, recent_from, previous_from)
    rows = query_rows(
        session,
        f"""select b.skill,
            count(*) filter (where j.first_seen_week >= :recent) as recent,
            count(*) filter (
                where j.first_seen_week >= :previous and j.first_seen_week < :recent
            ) as previous
        from ({jobs}) j join marts.bridge_job_skills b using (job_id)
        where j.has_full_text and j.first_seen_week >= :previous
        group by b.skill""",
        window,
    )
    changes = [
        {
            "skill": r.skill,
            "recent_share": r.recent / recent_jobs,
            "previous_share": r.previous / previous_jobs,
            "delta": r.recent / recent_jobs - r.previous / previous_jobs,
        }
        for r in rows
        if max(r.recent, r.previous) >= MIN_SKILL_JOBS
    ]
    changes.sort(key=lambda c: -c["delta"])
    return {
        "ready": True,
        "recent_from": recent_from,
        "previous_from": previous_from,
        "recent_jobs": recent_jobs,
        "previous_jobs": previous_jobs,
        "min_window_jobs": MIN_WINDOW_JOBS,
        "rising": [c for c in changes if c["delta"] > 0][:TOP_CHANGES],
        "falling": [c for c in reversed(changes) if c["delta"] < 0][:TOP_CHANGES],
    }


def _no_change(
    recent_jobs: int,
    previous_jobs: int,
    recent_from: date | None = None,
    previous_from: date | None = None,
) -> dict[str, Any]:
    return {
        "ready": False,
        "recent_from": recent_from,
        "previous_from": previous_from,
        "recent_jobs": recent_jobs,
        "previous_jobs": previous_jobs,
        "min_window_jobs": MIN_WINDOW_JOBS,
        "rising": [],
        "falling": [],
    }
