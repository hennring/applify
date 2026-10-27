"""Offline geocoding for German places (D11), from the GeoNames files in resources/."""

import math
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

RESOURCES = Path(__file__).parents[2] / "resources"

POSTAL_CODE = re.compile(r"(?<!\d)\d{5}(?!\d)")
# "Frankfurt am Main" is also found as "Frankfurt", "Halle (Saale)" as "Halle".
NAME_SUFFIX = re.compile(r"\s*\(.*\)|\s+(am|an der|in der|ob der|bei|im|vor der)\s.*$")


@dataclass(frozen=True)
class Place:
    name: str
    lat: float
    lon: float
    population: int = 0


def place_key(name: str) -> str:
    return re.sub(r"\s+", " ", name.casefold().replace("ß", "ss")).strip()


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance (haversine)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi, d_lambda = phi2 - phi1, math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


class Gazetteer:
    def __init__(self, places: list[Place], postal: dict[str, Place]) -> None:
        self.postal = postal
        # Ambiguous names resolve to the place with the largest population.
        self.by_name: dict[str, Place] = {}
        for place in places:
            for key in {place_key(place.name), place_key(NAME_SUFFIX.sub("", place.name))}:
                known = self.by_name.get(key)
                if key and (known is None or place.population > known.population):
                    self.by_name[key] = place

    @classmethod
    def from_files(cls, places_file: Path, postal_file: Path) -> "Gazetteer":
        places = [
            Place(name, float(lat), float(lon), int(population))
            for name, lat, lon, population in _read_tsv(places_file)
        ]
        postal = {
            code: Place(name, float(lat), float(lon))
            for code, name, lat, lon in _read_tsv(postal_file)
        }
        # Postal place names cover districts and small towns missing from the place list.
        return cls([*postal.values(), *places], postal)

    def locate(self, text: str) -> Place | None:
        """Place for free text like "04109 Leipzig", "Münster, Westfalen" or "Berlin-Mitte"."""
        if match := POSTAL_CODE.search(text):
            if place := self.postal.get(match.group()):
                return place
            text = POSTAL_CODE.sub("", text)
        for candidate in (text, text.split(",")[0], re.split(r"[-/]", text.split(",")[0])[0]):
            key = place_key(POSTAL_CODE.sub("", candidate))
            place = self.by_name.get(key) or self.by_name.get(place_key(NAME_SUFFIX.sub("", key)))
            if place:
                return place
        return None

    def city(self, text: str) -> str | None:
        """Name of the town in "Zentrum, Leipzig" or "Chemnitz, Sachsen": the most populous
        known place among the comma-separated parts."""
        found = [
            place
            for part in POSTAL_CODE.sub("", text).split(",")
            if (key := place_key(part))
            and (place := self.by_name.get(key) or self.by_name.get(NAME_SUFFIX.sub("", key)))
        ]
        return max(found, key=lambda p: p.population).name if found else None


def _read_tsv(path: Path) -> list[list[str]]:
    with path.open(encoding="utf-8") as f:
        return [line.rstrip("\n").split("\t") for line in f if not line.startswith("#")]


@lru_cache
def get_gazetteer() -> Gazetteer:
    return Gazetteer.from_files(
        RESOURCES / "geonames_places.tsv", RESOURCES / "geonames_postal.tsv"
    )
