"""Adzuna search API (F7b); needs a free API key (developer.adzuna.com).

Adzuna only delivers a text snippet, so its postings are short info (F8) unless dedup merges
them with the same job from a source with full text.
"""

from datetime import datetime
from typing import Any

from applify.sources.base import JobPosting, SearchQuery
from applify.sources.http import PoliteClient

API_URL = "https://api.adzuna.com/v1/api/jobs/de/search/{page}"
PAGE_SIZE = 50


def parse_posting(item: dict[str, Any]) -> JobPosting:
    created = item.get("created")
    predicted = str(item.get("salary_is_predicted", "0")) == "1"
    salary_min, salary_max = (None, None) if predicted else _salary(item)
    return JobPosting(
        source="adzuna",
        external_id=str(item["id"]),
        url=item.get("redirect_url") or "",
        title=item.get("title") or "",
        company=(item.get("company") or {}).get("display_name") or "",
        location_raw=(item.get("location") or {}).get("display_name") or "",
        lat=item.get("latitude"),
        lon=item.get("longitude"),
        salary_min=salary_min,
        salary_max=salary_max,
        description=item.get("description") or "",
        has_full_text=False,
        posted_at=datetime.fromisoformat(created) if created else None,
        raw={k: v for k, v in item.items() if k != "description"},
    )


def _salary(item: dict[str, Any]) -> tuple[int | None, int | None]:
    low, high = item.get("salary_min"), item.get("salary_max")
    return (int(low) if low else None, int(high) if high else None)


class AdzunaSource:
    name = "adzuna"
    label = "Adzuna"
    located = True

    def __init__(
        self, client: PoliteClient, app_id: str, app_key: str, *, max_pages: int = 2
    ) -> None:
        self.client = client
        self.auth = {"app_id": app_id, "app_key": app_key}
        self.max_pages = max_pages

    def search(self, query: SearchQuery) -> list[JobPosting]:
        params: dict[str, str | int] = {
            **self.auth,
            "what": query.term,
            "max_days_old": query.days,
            "results_per_page": PAGE_SIZE,
            "content-type": "application/json",
        }
        if query.location:
            params |= {"where": query.location, "distance": query.radius_km}
        postings: list[JobPosting] = []
        for page in range(1, self.max_pages + 1):
            data = self.client.get_json(API_URL.format(page=page), params=params)
            items = data.get("results") or []
            postings += [parse_posting(item) for item in items if item.get("id")]
            if len(items) < PAGE_SIZE or page * PAGE_SIZE >= data.get("count", 0):
                break
        return postings

    def complete(self, posting: JobPosting) -> JobPosting:
        return posting  # the redirect leads to third-party pages (D6)
