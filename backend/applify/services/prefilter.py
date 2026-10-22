"""Prefilter for sources that deliver more than the profile's places (§5.1).

Feeds and careers pages list every posting of a company or board; only postings within a
radius or remote-compatible are stored.
"""

import re

from applify.services.geo import Gazetteer, distance_km
from applify.services.matching import ProfilePlace
from applify.services.normalize import REMOTE_LOCATION, detect_remote
from applify.sources.base import JobPosting

# "Berlin, Hamburg", "München | Remote", "Köln oder Bonn"
PLACE_SEPARATOR = re.compile(r"\s*(?:[,;|/]|\bor\b|\boder\b|\bund\b)\s*", re.IGNORECASE)


class Prefilter:
    def __init__(self, places: list[ProfilePlace], remote_pref: str, gazetteer: Gazetteer) -> None:
        self.places = places
        self.remote_pref = remote_pref
        self.gazetteer = gazetteer

    def _points(self, posting: JobPosting) -> list[tuple[float, float]]:
        if posting.lat is not None and posting.lon is not None:
            return [(posting.lat, posting.lon)]
        points = []
        text = posting.location_raw
        for part in [text, *PLACE_SEPARATOR.split(text)]:
            if part and (place := self.gazetteer.locate(part)) is not None:
                points.append((place.lat, place.lon))
        return points

    def check(self, posting: JobPosting) -> bool | None:
        """True: keep, False: drop, None: place unknown so far (decide after the details)."""
        if posting.country and posting.country != "de":
            return False
        remote = posting.remote_type or (
            "remote"
            if REMOTE_LOCATION.search(posting.location_raw)
            else detect_remote(f"{posting.title}\n{posting.location_raw}")
        )
        if remote == "remote" and self.remote_pref == "remote":
            return True
        points = self._points(posting)
        if not points:
            return None
        if not self.places:  # no places in the profile: all of Germany
            return True
        return any(
            distance_km(lat, lon, p.lat, p.lon) <= p.radius_km
            for lat, lon in points
            for p in self.places
        )
