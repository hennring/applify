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
# A same-named place this far from a job's coordinates is another town.
SAME_PLACE_KM = 30
KREIS = re.compile(r"kreis", re.IGNORECASE)
# Several locations in one text: "Berlin; München", "Bonn / Berlin", "10117 Berlin, 20095 Hamburg".
LOCATIONS = re.compile(r"[;|]|\s(?:/|or)\s|,\s*(?=\d{5})", re.IGNORECASE)
# Not towns, though they contain place names: "Dresden, Sachsen", "Schleswig-Holstein".
STATES = {
    "baden-württemberg",
    "bayern",
    "brandenburg",
    "hessen",
    "mecklenburg-vorpommern",
    "niedersachsen",
    "nordrhein-westfalen",
    "rheinland-pfalz",
    "saarland",
    "sachsen",
    "sachsen-anhalt",
    "schleswig-holstein",
    "thüringen",
}
# Spelling of international postings, same town as the German name.
ENGLISH_NAMES = {"cologne": "köln", "munich": "münchen", "nuremberg": "nürnberg"}


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
        # All places with a known population per name, for the town size of a job.
        self.populated: dict[str, list[Place]] = {}
        for place in places:
            for key in {place_key(place.name), place_key(NAME_SUFFIX.sub("", place.name))}:
                known = self.by_name.get(key)
                if key and (known is None or place.population > known.population):
                    self.by_name[key] = place
                if key and place.population:
                    self.populated.setdefault(key, []).append(place)

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

    def _town(self, text: str) -> Place | None:
        """The place in one comma-separated part: "Leipzig", "Berlin-Mitte", "Berlin/Remote"."""
        # Cut off postal codes come as "28 Bremen".
        text = text.lstrip("0123456789 ")
        if place_key(text) in STATES:
            return None
        for candidate in (text, re.split(r"[-/]", text)[0]):
            key = place_key(candidate)
            key = ENGLISH_NAMES.get(key, key)
            place = self.by_name.get(key) or self.by_name.get(NAME_SUFFIX.sub("", key))
            if key and place:
                return place
        return None

    def cities(self, text: str) -> list[str]:
        """Names of the towns in free text, for filtering by town.

        A list names several ("Köln, München, Berlin"), but of two names the smaller is taken
        for a district ("Wedding, Berlin"). A Kreis counts only if no town is named ("Bünde,
        Herford (Kreis)"), the postal code only if no name is known.
        """
        names: list[str] = []
        for location in LOCATIONS.split(text):
            parts = POSTAL_CODE.sub("", location).split(",")
            towns = [
                place for part in parts if not KREIS.search(part) and (place := self._town(part))
            ] or [place for part in parts if (place := self._town(part))]
            if len(towns) == len(parts) == 2:
                towns = [max(towns, key=lambda p: p.population)]
            if not towns and (match := POSTAL_CODE.search(location)):
                towns = [place] if (place := self.postal.get(match.group())) else []
            names += [place.name for place in towns]
        return list(dict.fromkeys(names))

    def population(
        self, text: str, lat: float | None = None, lon: float | None = None
    ) -> int | None:
        """Inhabitants of the town in free text, None if unknown.

        Districts count as their city ("Zentrum, Leipzig", "Berlin-Mitte"): the largest place
        named in the text wins. With coordinates, same-named places far away are ignored.
        """
        # "Geiersthal, Regen (Kreis)": the district is named after another town.
        names = [
            name for name in re.split(r"[,;]", POSTAL_CODE.sub("", text)) if not KREIS.search(name)
        ]
        names += [re.split(r"[-/]", name)[0] for name in names]
        if (match := POSTAL_CODE.search(text)) and (place := self.postal.get(match.group())):
            names.append(place.name)
        found = [
            place
            for name in names
            if (key := place_key(name))
            for place in self.populated.get(key) or self.populated.get(NAME_SUFFIX.sub("", key), [])
            if lat is None
            or lon is None
            or distance_km(lat, lon, place.lat, place.lon) <= SAME_PLACE_KM
        ]
        return max(place.population for place in found) if found else None


def _read_tsv(path: Path) -> list[list[str]]:
    with path.open(encoding="utf-8") as f:
        return [line.rstrip("\n").split("\t") for line in f if not line.startswith("#")]


@lru_cache
def get_gazetteer() -> Gazetteer:
    return Gazetteer.from_files(
        RESOURCES / "geonames_places.tsv", RESOURCES / "geonames_postal.tsv"
    )
