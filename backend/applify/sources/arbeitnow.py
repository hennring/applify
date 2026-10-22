"""Arbeitnow job board API (F7b): German postings with full text, read page by page.

Spike 2026-10-21: 300 postings per page, newest first, `description` as HTML. Terms: "free
public API, please do not abuse", a link back is welcome (the UI links every posting).
"""

from datetime import UTC, datetime
from typing import Any

from applify.sources.base import JobPosting
from applify.sources.html_text import html_to_text
from applify.sources.http import PoliteClient

API_URL = "https://www.arbeitnow.com/api/job-board-api"
MIN_FULL_TEXT = 200


def parse_posting(item: dict[str, Any]) -> JobPosting:
    description = html_to_text(item.get("description") or "")
    created = item.get("created_at")
    return JobPosting(
        source="arbeitnow",
        external_id=item["slug"],
        url=item.get("url") or f"https://www.arbeitnow.com/view/{item['slug']}",
        title=item.get("title") or "",
        company=item.get("company_name") or "",
        location_raw=item.get("location") or "",
        remote_type="remote" if item.get("remote") else None,
        description=description,
        has_full_text=len(description) >= MIN_FULL_TEXT,
        posted_at=datetime.fromtimestamp(created, UTC) if isinstance(created, int) else None,
        raw={k: v for k, v in item.items() if k != "description"},
    )


class ArbeitnowSource:
    name = "arbeitnow"
    label = "Arbeitnow"

    def __init__(self, client: PoliteClient, *, max_pages: int = 4) -> None:
        self.client = client
        self.max_pages = max_pages

    def fetch(self) -> list[JobPosting]:
        postings: list[JobPosting] = []
        for page in range(1, self.max_pages + 1):
            data = self.client.get_json(API_URL, params={"page": page})
            postings += [parse_posting(item) for item in data.get("data") or [] if item.get("slug")]
            if not (data.get("links") or {}).get("next"):
                break
        return postings

    def complete(self, posting: JobPosting) -> JobPosting:
        return posting  # the feed carries the full text
