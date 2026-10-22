"""JobSource plugin interface (N4): one implementation per job source."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from applify.sources.http import PoliteClient


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
    country: str | None = None  # ISO 3166 alpha-2, lower case, if the source says
    salary_min: int | None = None
    salary_max: int | None = None
    description: str = ""
    has_full_text: bool = False
    posted_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class SourceError(Exception):
    """A request to a source failed; the run records it and continues (F7d)."""


class JobSource(Protocol):
    """A source searched per term and location."""

    name: str
    label: str
    # True if the source filters by location itself; otherwise the run applies the
    # location/remote prefilter to its results.
    located: bool

    def search(self, query: SearchQuery) -> list[JobPosting]:
        """Postings for one query; may contain only short info."""
        ...

    def complete(self, posting: JobPosting) -> JobPosting:
        """Fetch the full text for a posting that is new or lacks it."""
        ...


class FeedSource(Protocol):
    """A source read as a whole once per run; the run prefilters by location/remote."""

    name: str
    label: str

    def fetch(self) -> list[JobPosting]: ...

    def complete(self, posting: JobPosting) -> JobPosting: ...


@dataclass
class SourceConfig:
    """User settings of one source (table source_settings)."""

    enabled: bool = True
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunSources:
    """Everything a search run uses to reach the outside world."""

    sources: list[JobSource] = field(default_factory=list)
    feeds: list[FeedSource] = field(default_factory=list)
    # For careers pages, company detection and discovery; None skips those steps.
    client: "PoliteClient | None" = None


SourcesFactory = Callable[[dict[str, SourceConfig]], RunSources]
