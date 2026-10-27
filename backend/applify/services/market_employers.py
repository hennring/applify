"""Tab "Arbeitgeber" (§5.9): who posts the jobs of the selection.

Companies are grouped by their normalized name (legal form dropped), so "zollsoft GmbH"
and "zollsoft" count as one employer.
"""

from typing import Any

from sqlalchemy.orm import Session

from applify.services.market import MarketFilter, most_common, query_rows, selection_where

TOP_EMPLOYERS = 20
TOP_REPEATED = 15
# Seen again this many days after all earlier postings with the same title had vanished.
REPOST_GAP_DAYS = 7


def employers(session: Session, user_id: int, f: MarketFilter) -> dict[str, Any]:
    where, params = selection_where(f, user_id)
    jobs = f"select * from marts.fct_job_postings f where {where}"
    total, companies = query_rows(
        session,
        f"select count(*), count(distinct company_norm) from ({jobs}) j",
        params,
    )[0]
    top = query_rows(
        session,
        f"""select company_norm,
            mode() within group (order by company) as company,
            count(*) as jobs,
            count(*) filter (where is_active) as active,
            bool_or(is_agency) as agency,
            (array_agg(d.label order by d.sort_order) filter (where role_family <> 'unknown'))
                as roles
        from ({jobs}) j left join marts.dim_role_family d using (role_family)
        group by company_norm order by jobs desc, company_norm limit {TOP_EMPLOYERS}""",
        params,
    )
    top10 = sum(r.jobs for r in top[:10])
    agencies = query_rows(
        session,
        f"""select mode() within group (order by company) as company, count(*) as jobs
        from ({jobs}) j where is_agency
        group by company_norm order by jobs desc, company_norm limit 10""",
        params,
    )
    return {
        "jobs": total,
        "companies": companies,
        "top10_share": top10 / total if total else 0.0,
        "top": [{**r._mapping, "roles": most_common(r.roles)} for r in top],
        "agencies": [dict(r._mapping) for r in agencies],
        "repeated": _repeated(session, jobs, params),
    }


def _repeated(session: Session, jobs: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    """Titles a company posts more than once: in several places at once, or again later."""
    rows = query_rows(
        session,
        f"""with ordered as (
            select company_norm, title_norm, company, title, city_norm,
                first_seen_at, last_seen_at,
                max(last_seen_at) over (
                    partition by company_norm, title_norm order by first_seen_at, job_id
                    rows between unbounded preceding and 1 preceding
                ) as earlier_last_seen
            from ({jobs}) j
        )
        select
            mode() within group (order by company) as company,
            mode() within group (order by title) as title,
            count(*) as jobs,
            count(distinct nullif(city_norm, '')) as places,
            count(*) filter (
                where first_seen_at > earlier_last_seen + make_interval(days => :gap)
            ) as reposts,
            min(first_seen_at) as first_seen_at,
            max(last_seen_at) as last_seen_at
        from ordered
        group by company_norm, title_norm having count(*) > 1
        order by reposts desc, jobs desc, company, title limit {TOP_REPEATED}""",
        {**params, "gap": REPOST_GAP_DAYS},
    )
    return [dict(r._mapping) for r in rows]
