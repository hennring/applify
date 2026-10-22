"""Bundesagentur für Arbeit, Jobsuche-API (F6).

Verified in the M2 spike (2026-10-21): the search runs on v6 (v4 answers 403), the detail
with full text still on v4 under the base64-encoded reference number.
"""

import base64
from datetime import UTC, datetime
from typing import Any

from applify.sources.base import JobPosting, SearchQuery, SourceError
from applify.sources.http import PoliteClient

BASE_URL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service"
# Public key of the BA web app, documented at bund.dev.
API_KEY = "jobboerse-jobsuche"
PAGE_SIZE = 100
# Postings shorter than this are treated as short info (F8).
MIN_FULL_TEXT = 200


def job_url(refnr: str) -> str:
    return f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{refnr}"


def _salary(item: dict[str, Any]) -> tuple[int | None, int | None]:
    factor = {"JAHRESGEHALT": 1, "MONATSGEHALT": 12}.get(item.get("verguetungsangabe", ""))
    if factor is None:
        return None, None  # no information or hourly wage
    if "festgehalt" in item:
        value = int(item["festgehalt"] * factor)
        return value, value
    low, high = item.get("gehaltsspanneVon"), item.get("gehaltsspanneBis")
    return (
        int(low * factor) if low is not None else None,
        int(high * factor) if high is not None else None,
    )


def _remote(item: dict[str, Any]) -> str | None:
    if not item.get("homeofficemoeglich"):
        return None
    return "remote" if item.get("homeofficeprozent") == 100 else "hybrid"


def parse_posting(item: dict[str, Any]) -> JobPosting:
    refnr = item["referenznummer"]
    locations = item.get("stellenlokationen") or [{}]
    address = locations[0].get("adresse", {})
    published = item.get("datumErsteVeroeffentlichung") or item.get(
        "veroeffentlichungszeitraum", {}
    ).get("von")
    salary_min, salary_max = _salary(item)
    description = item.get("stellenangebotsBeschreibung") or ""
    return JobPosting(
        source="ba",
        external_id=refnr,
        url=job_url(refnr),
        title=item.get("stellenangebotsTitel") or item.get("hauptberuf") or "",
        company=item.get("firma") or "",
        location_raw=" ".join(filter(None, (address.get("plz"), address.get("ort")))),
        lat=locations[0].get("breite"),
        lon=locations[0].get("laenge"),
        remote_type=_remote(item),
        salary_min=salary_min,
        salary_max=salary_max,
        description=description,
        has_full_text=len(description) >= MIN_FULL_TEXT,
        posted_at=datetime.fromisoformat(published).replace(tzinfo=UTC) if published else None,
        # The text lives in jobs.description; raw keeps everything else.
        raw={k: v for k, v in item.items() if k != "stellenangebotsBeschreibung"},
    )


class ArbeitsagenturSource:
    name = "ba"
    label = "Bundesagentur für Arbeit"
    located = True

    def __init__(self, client: PoliteClient, *, max_pages: int = 2) -> None:
        self.client = client
        self.max_pages = max_pages
        self.headers = {"X-API-Key": API_KEY}

    def search(self, query: SearchQuery) -> list[JobPosting]:
        params: dict[str, str | int] = {
            "was": query.term,
            "angebotsart": 1,
            "veroeffentlichtseit": query.days,
            "size": PAGE_SIZE,
        }
        if query.location:
            params |= {"wo": query.location, "umkreis": query.radius_km}
        postings: list[JobPosting] = []
        for page in range(1, self.max_pages + 1):
            data = self.client.get_json(
                f"{BASE_URL}/pc/v6/jobs", params=params | {"page": page}, headers=self.headers
            )
            items = data.get("ergebnisliste") or []
            postings += [parse_posting(item) for item in items if item.get("referenznummer")]
            if len(items) < PAGE_SIZE or page * PAGE_SIZE >= data.get("maxErgebnisse", 0):
                break
        return postings

    def complete(self, posting: JobPosting) -> JobPosting:
        encoded = base64.b64encode(posting.external_id.encode()).decode()
        try:
            detail = self.client.get_json(
                f"{BASE_URL}/pc/v4/jobdetails/{encoded}", headers=self.headers
            )
        except SourceError:
            return posting  # keep the short info (F8)
        full = parse_posting({**posting.raw, **detail})
        # The search result knows the location matching the query; the detail lists all.
        full.location_raw, full.lat, full.lon = posting.location_raw, posting.lat, posting.lon
        return full
