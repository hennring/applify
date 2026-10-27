"""Build the outlines of the German states (§5.9): python -m applify_analytics.build_states

Reads the Natural Earth admin-1 dataset (public domain, naturalearthdata.com), simplifies
the 16 states and writes:
- resources/states.json: outlines in degrees, for assigning jobs to states;
- frontend/src/lib/viz/germanyStates.ts: SVG paths for the map on the market page.

Pass a local copy of ne_10m_admin_1_states_provinces.geojson as argument, or nothing to
download it (about 40 MB).
"""

import json
import math
import sys
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[2]
STATES_FILE = ROOT / "analytics" / "resources" / "states.json"
MAP_FILE = ROOT / "frontend" / "src" / "lib" / "viz" / "germanyStates.ts"
SOURCE_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
    "ne_10m_admin_1_states_provinces.geojson"
)
# Inhabitants in thousands (Destatis, 31.12.2023, rounded); for jobs per 100,000.
POPULATION = {
    "DE-BW": 11_280, "DE-BY": 13_370, "DE-BE": 3_660, "DE-BB": 2_570, "DE-HB": 690,
    "DE-HH": 1_860, "DE-HE": 6_390, "DE-MV": 1_630, "DE-NI": 8_140, "DE-NW": 18_140,
    "DE-RP": 4_160, "DE-SL": 990, "DE-SN": 4_090, "DE-ST": 2_170, "DE-SH": 2_960,
    "DE-TH": 2_120,
}  # fmt: skip
# Tolerance of the simplification in degrees (~1 km for assignment, ~3 km for the map).
ASSIGN_TOLERANCE = 0.01
MAP_TOLERANCE = 0.03
MAP_WIDTH = 500
# Equirectangular projection, scaled for the latitude of central Germany.
LAT_SCALE = math.cos(math.radians(51.0))

Ring = list[tuple[float, float]]


def simplify(ring: Ring, tolerance: float) -> Ring:
    """Douglas-Peucker on a closed ring; keeps at least a triangle."""

    def reduce(points: Ring) -> Ring:
        if len(points) < 3:
            return points
        (x1, y1), (x2, y2) = points[0], points[-1]
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy) or 1e-12
        distances = [abs(dy * x - dx * y + x2 * y1 - y2 * x1) / length for x, y in points[1:-1]]
        index = max(range(len(distances)), key=distances.__getitem__) + 1
        if distances[index - 1] <= tolerance:
            return [points[0], points[-1]]
        return reduce(points[: index + 1])[:-1] + reduce(points[index:])

    half = len(ring) // 2
    result = reduce(ring[: half + 1])[:-1] + reduce(ring[half:])
    return result if len(result) >= 4 else ring


def rings_of(geometry: dict[str, Any]) -> list[Ring]:
    polygons = geometry["coordinates"]
    if geometry["type"] == "Polygon":
        polygons = [polygons]
    return [[(x, y) for x, y in ring] for polygon in polygons for ring in polygon]


def load(source: str | None) -> list[dict[str, Any]]:
    if source:
        data = json.loads(Path(source).read_text(encoding="utf-8"))
    else:
        data = httpx.get(SOURCE_URL, timeout=300, follow_redirects=True).raise_for_status().json()
    return [f for f in data["features"] if f["properties"].get("iso_a2") == "DE"]


def main() -> None:
    features = load(sys.argv[1] if len(sys.argv) > 1 else None)
    states = sorted(
        (
            {
                "code": f["properties"]["iso_3166_2"],
                "name": f["properties"]["name"],
                "rings": rings_of(f["geometry"]),
            }
            for f in features
        ),
        key=lambda s: s["code"],
    )
    if {s["code"] for s in states} != set(POPULATION):
        raise SystemExit(f"unexpected states: {[s['code'] for s in states]}")

    STATES_FILE.write_text(
        json.dumps(
            [
                {
                    "code": s["code"],
                    "name": s["name"],
                    "population": POPULATION[s["code"]] * 1000,
                    "rings": [
                        [[round(x, 4), round(y, 4)] for x, y in simplify(r, ASSIGN_TOLERANCE)]
                        for r in s["rings"]
                    ],
                }
                for s in states
            ],
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    all_points = [p for s in states for r in s["rings"] for p in r]
    west, east = min(x for x, _ in all_points), max(x for x, _ in all_points)
    north = max(y for _, y in all_points)
    scale = MAP_WIDTH / ((east - west) * LAT_SCALE)

    def project(x: float, y: float) -> tuple[float, float]:
        return ((x - west) * LAT_SCALE * scale, (north - y) * scale)

    height = round((north - min(y for _, y in all_points)) * scale)
    entries = []
    for s in states:
        rings = [simplify(r, MAP_TOLERANCE) for r in s["rings"]]
        # Drop specks (small islands) that would be invisible anyway.
        rings = [r for r in rings if len(r) >= 4]
        path = " ".join(
            "M" + "L".join(f"{px:.1f},{py:.1f}" for px, py in (project(x, y) for x, y in r)) + "Z"
            for r in rings
        )
        largest = max(s["rings"], key=len)
        cx, cy = project(
            sum(x for x, _ in largest) / len(largest), sum(y for _, y in largest) / len(largest)
        )
        entries.append(
            f"\t{{ code: '{s['code']}', name: '{s['name']}', "
            f"x: {cx:.0f}, y: {cy:.0f}, path: '{path}' }}"
        )
    MAP_FILE.write_text(
        "// Generated by analytics/applify_analytics/build_states.py from Natural Earth\n"
        "// (public domain); do not edit by hand.\n\n"
        f"export const MAP_WIDTH = {MAP_WIDTH};\nexport const MAP_HEIGHT = {height};\n\n"
        "export type StateShape = { code: string; name: string; x: number; y: number; "
        "path: string };\n\n"
        "export const STATES: StateShape[] = [\n" + ",\n".join(entries) + "\n];\n",
        encoding="utf-8",
    )
    print(f"{len(states)} states written to {STATES_FILE.name} and {MAP_FILE.name}")


if __name__ == "__main__":
    main()
