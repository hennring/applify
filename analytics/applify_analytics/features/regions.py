"""Federal state of each job (§5.9), from its coordinates and the state outlines.

The outlines (resources/states.json) come from build_states; the coordinates are the ones
Applify's gazetteer found for the job's place, so jobs without a known German place have
no state.
"""

import json
import math
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from applify.db.models import Job
from sqlalchemy import Column, Integer, String, Table, delete, insert, select
from sqlalchemy.engine import Connection

from applify_analytics.features.store import ensure_tables, metadata

STATES_FILE = Path(__file__).resolve().parents[2] / "resources" / "states.json"
# City states lie inside other states' outlines; they are tested first.
CITY_STATES = ("DE-BE", "DE-HB", "DE-HH")
# Points just outside every outline (coast, simplified border) go to the nearest state.
MAX_OUTSIDE_KM = 15.0

Ring = list[tuple[float, float]]

states = Table(
    "states",
    metadata,
    Column("state_code", String(5), primary_key=True),
    Column("name", String(50), nullable=False),
    Column("population", Integer, nullable=False),
)
job_regions = Table(
    "job_regions",
    metadata,
    Column("job_id", Integer, primary_key=True),
    Column("state_code", String(5), nullable=False),
)


@dataclass(frozen=True)
class State:
    code: str
    name: str
    population: int
    rings: tuple[Ring, ...]

    def contains(self, lon: float, lat: float) -> bool:
        """Even-odd rule over all rings, so holes (Berlin in Brandenburg) are respected."""
        inside = False
        for ring in self.rings:
            for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1], strict=True):
                if (y1 > lat) != (y2 > lat) and lon < x1 + (lat - y1) * (x2 - x1) / (y2 - y1):
                    inside = not inside
        return inside

    def distance_km(self, lon: float, lat: float) -> float:
        """Distance to the nearest outline point; enough for points just outside."""
        return min(_km(lon, lat, x, y) for ring in self.rings for x, y in ring)


def _km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    dx = math.radians(lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2))
    return 6371.0 * math.hypot(dx, math.radians(lat2 - lat1))


@cache
def get_states(path: Path = STATES_FILE) -> tuple[State, ...]:
    data = json.loads(path.read_text(encoding="utf-8"))
    loaded = [
        State(
            s["code"],
            s["name"],
            s["population"],
            tuple([(x, y) for x, y in ring] for ring in s["rings"]),
        )
        for s in data
    ]
    return tuple(sorted(loaded, key=lambda s: s.code not in CITY_STATES))


def state_at(lon: float, lat: float) -> str | None:
    for state in get_states():
        if state.contains(lon, lat):
            return state.code
    nearest = min(get_states(), key=lambda s: s.distance_km(lon, lat))
    return nearest.code if nearest.distance_km(lon, lat) <= MAX_OUTSIDE_KM else None


def refresh_states(conn: Connection) -> int:
    rows = [
        {"state_code": s.code, "name": s.name, "population": s.population} for s in get_states()
    ]
    conn.execute(delete(states))
    conn.execute(insert(states), rows)
    return len(rows)


def refresh_job_regions(conn: Connection) -> int:
    """State of every job with coordinates; rebuilt each run (fast, locations can change)."""
    ensure_tables(conn)
    rows = []
    for job_id, lat, lon in conn.execute(select(Job.id, Job.lat, Job.lon)):
        if lat is not None and lon is not None and (code := state_at(lon, lat)) is not None:
            rows.append({"job_id": job_id, "state_code": code})
    conn.execute(delete(job_regions))
    if rows:
        conn.execute(insert(job_regions), rows)
    return len(rows)
