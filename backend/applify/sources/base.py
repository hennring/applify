"""JobSource plugin interface (N4): one implementation per job source."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol


@dataclass(frozen=True)
class SearchQuery:
    term: str
    # None searches without a location (whole Germany).
    location: str | None
    radius_km: int
    # Only postings published within the last N days.
    days: int = 30


@dataclass
class JobPosting:
    """A posting as delivered by one source, before normalization and dedup."""

    source: str
    external_id: str
    url: str
    title: str
    company: str
    location_raw: str = ""
    lat: float | None = None
    lon: float | None = None
    remote_type: str | None = None  # hybrid / remote
    salary_min: int | None = None
    salary_max: int | None = None
    description: str = ""
    has_full_text: bool = False
    posted_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class SourceError(Exception):
    """A request to a source failed; the run records it and continues (F7d)."""


class JobSource(Protocol):
    name: str
    label: str

    def search(self, query: SearchQuery) -> list[JobPosting]:
        """Postings for one query; may contain only short info."""
        ...

    def complete(self, posting: JobPosting) -> JobPosting:
        """Fetch the full text for a posting that is new or lacks it."""
        ...


SourcesFactory = Callable[[], list[JobSource]]
