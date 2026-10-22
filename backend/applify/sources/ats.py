"""Careers pages via public ATS feeds (F7, D15): one adapter per applicant tracking system.

Endpoints verified in the M2 spike and again on 2026-10-22 (fixtures in tests/fixtures/ats).
A posting's external id is prefixed with the company token, so ids stay unique per source.
"""

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from html import unescape
from typing import Any, ClassVar, Protocol

from applify.sources.base import JobPosting, SourceError
from applify.sources.html_text import html_to_text
from applify.sources.http import PoliteClient

MIN_FULL_TEXT = 200


@dataclass
class Feed:
    """One company's feed in one run: token in, ETag in and out (N6)."""

    token: str
    company: str
    terms: list[str] = field(default_factory=list)
    etag: str | None = None
    unchanged: bool = False


class AtsAdapter(Protocol):
    type: str
    label: str

    def fetch(self, client: PoliteClient, feed: Feed) -> list[JobPosting]: ...

    def complete(self, client: PoliteClient, posting: JobPosting) -> JobPosting: ...

    def probe(self, client: PoliteClient, token: str) -> str | None:
        """Company name behind a guessed token, None if there is no such board."""
        ...


def _posting(adapter: str, token: str, item_id: object, **fields: Any) -> JobPosting:
    posting = JobPosting(source=f"ats:{adapter}", external_id=f"{token}:{item_id}", **fields)
    posting.has_full_text = len(posting.description) >= MIN_FULL_TEXT
    return posting


def _iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace(" UTC", "+00:00").replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _sections(parts: list[tuple[str, str]]) -> str:
    """Titled HTML sections → one text with ## headings."""
    texts = []
    for title, html in parts:
        if text := html_to_text(html or ""):
            texts.append(f"## {title}\n\n{text}" if title else text)
    return "\n\n".join(texts)


def _fetch(client: PoliteClient, url: str, feed: Feed, **kwargs: Any) -> Any:
    response = client.get_conditional(url, feed.etag, **kwargs)
    if response is None:
        feed.unchanged = True
        return None
    feed.etag = response.headers.get("etag")
    return response


# --- Personio ---------------------------------------------------------------------------


class Personio:
    type = "personio"
    label = "Personio"

    # Boards live on .de or .com; the link the token was found in does not always say which.
    DOMAINS = ("de", "com")

    def _url(self, token: str, domain: str = "de") -> str:
        return f"https://{token}.jobs.personio.{domain}/xml?language=de"

    def parse(self, token: str, content: bytes, domain: str = "de") -> list[JobPosting]:
        try:
            root = ET.fromstring(content)
        except ET.ParseError as exc:
            raise SourceError(f"Personio {token}: ungültiges XML") from exc
        postings = []
        for position in root.iter("position"):
            item_id = position.findtext("id")
            if not item_id:
                continue
            offices = [position.findtext("office") or ""] + [
                o.text or "" for o in position.iterfind("additionalOffices/office")
            ]
            description = _sections(
                [
                    (d.findtext("name") or "", d.findtext("value") or "")
                    for d in position.iterfind("jobDescriptions/jobDescription")
                ]
            )
            postings.append(
                _posting(
                    self.type,
                    token,
                    item_id,
                    url=f"https://{token}.jobs.personio.{domain}/job/{item_id}",
                    title=position.findtext("name") or "",
                    company=position.findtext("subcompany") or "",
                    location_raw=", ".join(o for o in offices if o),
                    description=description,
                    posted_at=_iso(position.findtext("createdAt")),
                    raw={
                        k: position.findtext(k)
                        for k in ("department", "employmentType", "seniority", "schedule")
                    },
                )
            )
        return postings

    def fetch(self, client: PoliteClient, feed: Feed) -> list[JobPosting]:
        for domain in self.DOMAINS:
            try:
                response = _fetch(client, self._url(feed.token, domain), feed)
                break
            except SourceError as exc:
                if "404" not in str(exc) or domain == self.DOMAINS[-1]:
                    raise
        if response is None:
            return []
        postings = self.parse(feed.token, response.content, domain)
        for posting in postings:
            posting.company = posting.company or feed.company
        return postings

    def complete(self, client: PoliteClient, posting: JobPosting) -> JobPosting:
        return posting

    def probe(self, client: PoliteClient, token: str) -> str | None:
        response = client.request("GET", self._url(token))
        if response.status_code == 404:
            response = client.request("GET", self._url(token, "com"))
        if response.status_code != 200 or b"<workzag-jobs" not in response.content[:500]:
            return None
        postings = self.parse(token, response.content)
        return next((p.company for p in postings if p.company), None)


# --- Greenhouse -------------------------------------------------------------------------


class Greenhouse:
    type = "greenhouse"
    label = "Greenhouse"
    API = "https://boards-api.greenhouse.io/v1/boards"

    def parse(self, token: str, data: dict[str, Any]) -> list[JobPosting]:
        return [
            _posting(
                self.type,
                token,
                item["id"],
                url=item.get("absolute_url") or "",
                title=item.get("title") or "",
                company=item.get("company_name") or "",
                location_raw=(item.get("location") or {}).get("name") or "",
                # The content is HTML, escaped once more.
                description=html_to_text(unescape(item.get("content") or "")),
                posted_at=_iso(item.get("first_published") or item.get("updated_at")),
                raw={"requisition_id": item.get("requisition_id")},
            )
            for item in data.get("jobs") or []
            if item.get("id")
        ]

    def fetch(self, client: PoliteClient, feed: Feed) -> list[JobPosting]:
        url = f"{self.API}/{feed.token}/jobs"
        response = _fetch(client, url, feed, params={"content": "true"})
        if response is None:
            return []
        postings = self.parse(feed.token, response.json())
        for posting in postings:
            posting.company = posting.company or feed.company
        return postings

    def complete(self, client: PoliteClient, posting: JobPosting) -> JobPosting:
        return posting

    def probe(self, client: PoliteClient, token: str) -> str | None:
        response = client.request("GET", f"{self.API}/{token}")
        return response.json().get("name") if response.status_code == 200 else None


# --- Lever ------------------------------------------------------------------------------


class Lever:
    type = "lever"
    label = "Lever"
    WORKPLACE: ClassVar[dict[str, str]] = {"remote": "remote", "hybrid": "hybrid"}

    def parse(self, token: str, items: list[dict[str, Any]], company: str) -> list[JobPosting]:
        postings = []
        for item in items:
            if not item.get("id"):
                continue
            categories = item.get("categories") or {}
            locations = categories.get("allLocations") or [categories.get("location") or ""]
            parts = [("", item.get("description") or "")]
            parts += [
                (lst.get("text") or "", lst.get("content") or "") for lst in item.get("lists") or []
            ]
            parts.append(("", item.get("additional") or ""))
            created = item.get("createdAt")
            postings.append(
                _posting(
                    self.type,
                    token,
                    item["id"],
                    url=item.get("hostedUrl") or "",
                    title=item.get("text") or "",
                    company=company,
                    location_raw=", ".join(filter(None, locations)),
                    remote_type=self.WORKPLACE.get(item.get("workplaceType") or ""),
                    country=(item.get("country") or "").lower() or None,
                    description=_sections(parts),
                    posted_at=datetime.fromtimestamp(created / 1000, UTC) if created else None,
                    raw={"categories": categories},
                )
            )
        return postings

    def fetch(self, client: PoliteClient, feed: Feed) -> list[JobPosting]:
        url = f"https://api.lever.co/v0/postings/{feed.token}"
        response = _fetch(client, url, feed, params={"mode": "json"})
        return [] if response is None else self.parse(feed.token, response.json(), feed.company)

    def complete(self, client: PoliteClient, posting: JobPosting) -> JobPosting:
        return posting

    def probe(self, client: PoliteClient, token: str) -> str | None:
        return None  # the feed names no company, so a guessed token cannot be verified


# --- Recruitee --------------------------------------------------------------------------


class Recruitee:
    type = "recruitee"
    label = "Recruitee"

    def _url(self, token: str) -> str:
        return f"https://{token}.recruitee.com/api/offers"

    def parse(self, token: str, data: dict[str, Any]) -> list[JobPosting]:
        postings = []
        for item in data.get("offers") or []:
            if not item.get("id"):
                continue
            salary = item.get("salary") or {}
            factor = {"year": 1, "month": 12}.get(salary.get("period") or "")
            low, high = salary.get("min"), salary.get("max")
            remote = "remote" if item.get("remote") else "hybrid" if item.get("hybrid") else None
            postings.append(
                _posting(
                    self.type,
                    token,
                    item["id"],
                    url=item.get("careers_url") or "",
                    title=item.get("title") or "",
                    company=item.get("company_name") or "",
                    location_raw=item.get("location") or item.get("city") or "",
                    remote_type=remote,
                    country=(item.get("country_code") or "").lower() or None,
                    salary_min=int(float(low) * factor) if factor and low else None,
                    salary_max=int(float(high) * factor) if factor and high else None,
                    description=_sections(
                        [("", item.get("description") or ""), ("", item.get("requirements") or "")]
                    ),
                    posted_at=_iso(item.get("published_at")),
                    raw={"department": item.get("department")},
                )
            )
        return postings

    def fetch(self, client: PoliteClient, feed: Feed) -> list[JobPosting]:
        response = _fetch(client, self._url(feed.token), feed)
        return [] if response is None else self.parse(feed.token, response.json())

    def complete(self, client: PoliteClient, posting: JobPosting) -> JobPosting:
        return posting

    def probe(self, client: PoliteClient, token: str) -> str | None:
        response = client.request("GET", self._url(token))
        if response.status_code != 200:
            return None
        offers = response.json().get("offers") or []
        return offers[0].get("company_name") if offers else None


# --- SmartRecruiters --------------------------------------------------------------------


class SmartRecruiters:
    type = "smartrecruiters"
    label = "SmartRecruiters"
    API = "https://api.smartrecruiters.com/v1/companies"
    PAGE_SIZE = 100
    MAX_PAGES = 5

    def parse_item(self, token: str, item: dict[str, Any]) -> JobPosting:
        location = item.get("location") or {}
        remote = (
            "remote" if location.get("remote") else "hybrid" if location.get("hybrid") else None
        )
        lat, lon = location.get("latitude"), location.get("longitude")
        sections = ((item.get("jobAd") or {}).get("sections")) or {}
        description = _sections(
            [
                (s.get("title") or "", s.get("text") or "")
                for key in ("jobDescription", "qualifications", "additionalInformation")
                if (s := sections.get(key))
            ]
        )
        return _posting(
            self.type,
            token,
            item["id"],
            url=item.get("postingUrl") or f"https://jobs.smartrecruiters.com/{token}/{item['id']}",
            title=item.get("name") or "",
            company=(item.get("company") or {}).get("name") or "",
            location_raw=" ".join(filter(None, (location.get("postalCode"), location.get("city")))),
            lat=float(lat) if lat else None,
            lon=float(lon) if lon else None,
            remote_type=remote,
            country=location.get("country"),
            description=description,
            posted_at=_iso(item.get("releasedDate")),
            raw={"refNumber": item.get("refNumber")},
        )

    def fetch(self, client: PoliteClient, feed: Feed) -> list[JobPosting]:
        postings: list[JobPosting] = []
        for page in range(self.MAX_PAGES):
            data = client.get_json(
                f"{self.API}/{feed.token}/postings",
                params={"limit": self.PAGE_SIZE, "offset": page * self.PAGE_SIZE, "country": "de"},
            )
            items = data.get("content") or []
            postings += [self.parse_item(feed.token, item) for item in items if item.get("id")]
            if (page + 1) * self.PAGE_SIZE >= data.get("totalFound", 0):
                break
        return postings

    def complete(self, client: PoliteClient, posting: JobPosting) -> JobPosting:
        token, item_id = posting.external_id.split(":", 1)
        try:
            detail = client.get_json(f"{self.API}/{token}/postings/{item_id}")
        except SourceError:
            return posting
        full = self.parse_item(token, detail)
        return full if full.description else posting

    def probe(self, client: PoliteClient, token: str) -> str | None:
        response = client.request("GET", f"{self.API}/{token}/postings", params={"limit": 1})
        if response.status_code != 200:
            return None
        items = response.json().get("content") or []
        return (items[0].get("company") or {}).get("name") if items else None


# --- Workday ----------------------------------------------------------------------------

POSTED = re.compile(r"(\d+)\+? Days? Ago", re.IGNORECASE)


def _posted_on(text: str, today: date) -> datetime | None:
    """Workday only says "Posted Today", "Posted Yesterday" or "Posted 3 Days Ago"."""
    if "today" in text.lower():
        days = 0
    elif "yesterday" in text.lower():
        days = 1
    elif match := POSTED.search(text):
        days = int(match.group(1))
    else:
        return None
    return datetime.combine(today - timedelta(days=days), datetime.min.time(), UTC)


class Workday:
    """Public but undocumented endpoint, so every field is optional here (§5.1, §7).

    Token: "tenant/wdN/site", e.g. "db/wd3/DBWebsite". The listing is searched with the
    run's terms, since big tenants have thousands of postings.
    """

    type = "workday"
    label = "Workday"
    PAGE_SIZE = 20
    MAX_PAGES = 2

    def _base(self, token: str) -> tuple[str, str]:
        tenant, wd, site = token.split("/")
        host = f"https://{tenant}.{wd}.myworkdayjobs.com"
        return f"{host}/wday/cxs/{tenant}/{site}", f"{host}/{site}"

    def fetch(self, client: PoliteClient, feed: Feed) -> list[JobPosting]:
        api, public = self._base(feed.token)
        today = datetime.now(UTC).date()
        postings: dict[str, JobPosting] = {}
        for term in feed.terms or [""]:
            for page in range(self.MAX_PAGES):
                response = client.request(
                    "POST",
                    f"{api}/jobs",
                    json={
                        "limit": self.PAGE_SIZE,
                        "offset": page * self.PAGE_SIZE,
                        "searchText": term,
                        "appliedFacets": {},
                    },
                )
                if response.status_code != 200:
                    raise SourceError(f"Workday {feed.token}: HTTP {response.status_code}")
                data = response.json()
                items = data.get("jobPostings") or []
                for item in items:
                    path = item.get("externalPath")
                    if not path or path in postings:
                        continue
                    postings[path] = _posting(
                        self.type,
                        feed.token,
                        path,
                        url=f"{public}{path}",
                        title=item.get("title") or "",
                        company=feed.company,
                        location_raw=item.get("locationsText") or "",
                        posted_at=_posted_on(item.get("postedOn") or "", today),
                        raw={"bulletFields": item.get("bulletFields")},
                    )
                if (page + 1) * self.PAGE_SIZE >= data.get("total", 0):
                    break
        return list(postings.values())

    def complete(self, client: PoliteClient, posting: JobPosting) -> JobPosting:
        token, path = posting.external_id.split(":", 1)
        api, _ = self._base(token)
        try:
            info = client.get_json(f"{api}{path}").get("jobPostingInfo") or {}
        except (SourceError, AttributeError):
            return posting
        country = ((info.get("jobRequisitionLocation") or {}).get("country") or {}).get(
            "alpha2Code"
        )
        posting.description = html_to_text(info.get("jobDescription") or "")
        posting.has_full_text = len(posting.description) >= MIN_FULL_TEXT
        posting.location_raw = info.get("location") or posting.location_raw
        posting.country = country.lower() if country else posting.country
        posting.url = info.get("externalUrl") or posting.url
        if start := info.get("startDate"):
            posting.posted_at = _iso(start) or posting.posted_at
        return posting

    def probe(self, client: PoliteClient, token: str) -> str | None:
        return None


ADAPTERS: dict[str, AtsAdapter] = {
    a.type: a
    for a in (Personio(), Greenhouse(), Lever(), Recruitee(), SmartRecruiters(), Workday())
}
# Adapters whose guessed tokens can be verified by the company name in the feed.
PROBE_ORDER = ("personio", "greenhouse", "recruitee", "smartrecruiters")

# ATS links on careers pages and in postings → (type, token).
ATS_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("personio", re.compile(r"\b([a-z0-9][a-z0-9-]*)\.jobs\.personio\.(?:de|com)", re.I)),
    (
        "greenhouse",
        re.compile(
            r"(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/(?:embed/job_board(?:/js)?\?for=)?"
            r"([A-Za-z0-9_-]+)"
            r"|boards-api\.greenhouse\.io/v1/boards/([A-Za-z0-9_-]+)",
            re.I,
        ),
    ),
    (
        "lever",
        re.compile(r"(?:jobs|api)\.(?:eu\.)?lever\.co/(?:v0/postings/)?([A-Za-z0-9_.-]+)", re.I),
    ),
    ("recruitee", re.compile(r"\b([a-z0-9][a-z0-9-]*)\.recruitee\.com", re.I)),
    (
        "smartrecruiters",
        re.compile(
            r"(?:jobs|careers)\.smartrecruiters\.com/([A-Za-z0-9_-]+)"
            r"|api\.smartrecruiters\.com/v1/companies/([A-Za-z0-9_-]+)",
            re.I,
        ),
    ),
    (
        "workday",
        re.compile(
            r"\b([a-z0-9-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([A-Za-z0-9_-]+)",
        ),
    ),
]
# Path segments that look like tokens but are not.
NOT_TOKENS = frozenset(
    [
        "www",
        "app",
        "api",
        "embed",
        "js",
        "v0",
        "v1",
        "wday",
        "jobs",
        "careers",
        "search",
        "static",
        "assets",
        "cdn",
        "widget",
    ]
)


def find_ats(text: str) -> tuple[str, str] | None:
    """The first ATS board referenced in a URL or page source."""
    for ats_type, pattern in ATS_PATTERNS:
        for match in pattern.finditer(text):
            groups = [g for g in match.groups() if g]
            if ats_type == "workday":
                if len(groups) == 3 and groups[2].lower() not in NOT_TOKENS:
                    return ats_type, "/".join(groups)
                continue
            if groups and groups[0].lower() not in NOT_TOKENS:
                token = groups[0]
                return ats_type, token.lower() if ats_type in ("personio", "recruitee") else token
    return None
