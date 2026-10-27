"""Tab "Regionen" (§5.9): where the jobs of the selection are."""

from typing import Any

from sqlalchemy.orm import Session

from applify.services.geo import get_gazetteer
from applify.services.market import MarketFilter, query_rows, selection_where

TOP_CITIES = 15
DISTANCE_BUCKETS = (
    ("< 10 km", 0, 10),
    ("10–25 km", 10, 25),
    ("25–50 km", 25, 50),
    ("50–100 km", 50, 100),
    ("100–250 km", 100, 250),
    ("> 250 km", 250, 100_000),
)


def regions(session: Session, user_id: int, f: MarketFilter) -> dict[str, Any]:
    where, params = selection_where(f, user_id)
    jobs = f"select * from marts.fct_job_postings f where {where}"
    states = query_rows(
        session,
        f"""select s.state_code, s.state_name, s.population, count(j.job_id) as jobs,
            count(j.job_id) filter (where j.remote_type = 'remote') as remote
        from marts.dim_state s left join ({jobs}) j using (state_code)
        group by s.state_code, s.state_name, s.population
        order by jobs desc, s.state_name""",
        params,
    )
    without = query_rows(
        session,
        f"""select count(*) filter (where state_code is null and scope = 'abroad') as abroad,
            count(*) filter (where state_code is null and scope <> 'abroad') as unknown,
            count(*) filter (where state_code is null and remote_type = 'remote') as remote
        from ({jobs}) j""",
        params,
    )[0]
    places = query_rows(
        session,
        f"""select location_raw, state_code, count(*) as jobs
        from ({jobs}) j where state_code is not null group by 1, 2""",
        params,
    )
    distances = [
        r.distance_km
        for r in query_rows(
            session,
            f"""select d.distance_km from ({jobs}) j
            join marts.fct_job_profile_distance d
                on d.job_id = j.job_id and d.user_id = :user_id""",
            params,
        )
    ]
    return {
        "states": [
            {**r._mapping, "per_100k": r.jobs / r.population * 100_000 if r.population else 0.0}
            for r in states
        ],
        "abroad": without.abroad,
        "unknown": without.unknown,
        "remote_without_place": without.remote,
        "cities": _cities(places),
        "distances": [
            {"bucket": label, "jobs": sum(low <= d < high for d in distances)}
            for label, low, high in DISTANCE_BUCKETS
        ],
    }


def _cities(places: list[Any]) -> list[dict[str, Any]]:
    """Jobs per town; districts ("Zentrum, Leipzig") count for their town."""
    gazetteer = get_gazetteer()
    towns: dict[tuple[str, str], int] = {}
    for r in places:
        name = gazetteer.city(r.location_raw) or r.location_raw.split(",")[0].strip()
        towns[name, r.state_code] = towns.get((name, r.state_code), 0) + r.jobs
    top = sorted(towns.items(), key=lambda t: (-t[1], t[0][0]))[:TOP_CITIES]
    return [{"city": city, "state_code": state, "jobs": jobs} for (city, state), jobs in top]
