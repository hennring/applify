"""Generic careers pages: schema.org/JobPosting as JSON-LD, job URLs from links and sitemap.xml.

Many employers embed JobPosting JSON-LD for Google for Jobs (D15); that gives title, place,
salary, date and full text without a page-specific scraper.
"""

import json
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from datetime import UTC, datetime
from html import unescape
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

from applify.sources.base import JobPosting, SourceError
from applify.sources.html_text import html_to_text
from applify.sources.http import PoliteClient, join_url

SCRIPT = re.compile(
    r"<script[^>]+type\s*=\s*[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", re.S | re.I
)
HREF = re.compile(r"<a\s[^>]*href\s*=\s*[\"']([^\"'#]+)", re.I)
# URL paths that point to single postings rather than overview pages.
JOB_PATH = re.compile(
    r"/(?:jobs?|stellen(?:angebote?)?|karriere|careers?|vacanc(?:y|ies)|offene-stellen|"
    r"positions?|stellenanzeigen?)/[^?#]*[a-z0-9-]{6,}",
    re.I,
)
SALARY_UNIT = {"YEAR": 1, "MONTH": 12}
MIN_FULL_TEXT = 200
# Per company and run: postings read from single pages (only new URLs cost a request).
MAX_JOB_PAGES = 30


def _objects(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, list):
        for item in value:
            yield from _objects(item)
    elif isinstance(value, dict):
        yield value
        yield from _objects(value.get("@graph"))


def job_postings(html: str) -> list[dict[str, Any]]:
    """All JobPosting objects in the JSON-LD blocks of a page."""
    found = []
    for block in SCRIPT.findall(html):
        try:
            data = json.loads(block.strip(), strict=False)
        except ValueError:
            continue
        for obj in _objects(data):
            kind = obj.get("@type")
            if kind == "JobPosting" or (isinstance(kind, list) and "JobPosting" in kind):
                found.append(obj)
    return found


def _first(value: Any) -> Any:
    return value[0] if isinstance(value, list) and value else value


def _text(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("name") or value.get("value")
    return str(value).strip() if value not in (None, "") else ""


def _number(value: Any) -> float | None:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _salary(base: Any) -> tuple[int | None, int | None]:
    base = _first(base)
    if not isinstance(base, dict):
        return None, None
    value = base.get("value")
    if not isinstance(value, dict):
        value = {"value": value}
    factor = SALARY_UNIT.get(str(value.get("unitText") or base.get("unitText") or "").upper())
    if factor is None:
        return None, None
    low = _number(value.get("minValue") or value.get("value"))
    high = _number(value.get("maxValue") or value.get("value"))
    return (
        int(low * factor) if low else None,
        int(high * factor) if high else None,
    )


def _country(value: str) -> str | None:
    value = value.strip().lower()
    if value in ("deutschland", "germany"):
        return "de"
    return value if len(value) == 2 else None


def _date(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def parse_posting(obj: dict[str, Any], page_url: str, company: str) -> JobPosting:
    places = obj.get("jobLocation")
    places = places if isinstance(places, list) else [places] if places else []
    names, country, lat, lon = [], None, None, None
    for place in places:
        if not isinstance(place, dict):
            continue
        address = place.get("address") or {}
        if isinstance(address, dict):
            names.append(
                " ".join(
                    filter(
                        None,
                        (_text(address.get("postalCode")), _text(address.get("addressLocality"))),
                    )
                )
            )
            country = country or _country(_text(address.get("addressCountry")))
        geo = place.get("geo") or {}
        if isinstance(geo, dict) and lat is None:
            lat, lon = _number(geo.get("latitude")), _number(geo.get("longitude"))
    remote = "remote" if "TELECOMMUTE" in str(obj.get("jobLocationType") or "").upper() else None
    identifier = obj.get("identifier")
    url = _text(obj.get("url")) or page_url
    description = html_to_text(unescape(_text(obj.get("description"))))
    salary_min, salary_max = _salary(obj.get("baseSalary"))
    return JobPosting(
        source="jsonld",
        external_id=(_text(identifier.get("value")) if isinstance(identifier, dict) else "") or url,
        url=url,
        title=html_to_text(_text(obj.get("title"))),
        company=_text(obj.get("hiringOrganization")) or company,
        location_raw=", ".join(n for n in names if n),
        lat=lat,
        lon=lon,
        remote_type=remote,
        country=country,
        salary_min=salary_min,
        salary_max=salary_max,
        description=description,
        has_full_text=len(description) >= MIN_FULL_TEXT,
        posted_at=_date(obj.get("datePosted")),
        raw={"validThrough": obj.get("validThrough"), "employmentType": obj.get("employmentType")},
    )


def _clean(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))


def job_links(html: str, page_url: str) -> list[str]:
    """Links on a careers page that look like single postings on the same site."""
    host = urlsplit(page_url).netloc
    links: dict[str, None] = {}
    for href in HREF.findall(html):
        joined = join_url(page_url, unescape(href))
        if joined is None:
            continue
        url = _clean(joined)
        if urlsplit(url).netloc == host and JOB_PATH.search(urlsplit(url).path):
            links[url] = None
    return list(links)


def sitemap_job_urls(client: PoliteClient, site: str, *, limit: int = 200) -> list[str]:
    """Posting URLs from the site's sitemap (one level of sitemap indexes)."""
    queue, urls, seen = [urljoin(site, "/sitemap.xml")], [], set[str]()
    while queue and len(seen) < 5:
        sitemap = queue.pop(0)
        seen.add(sitemap)
        try:
            root = ET.fromstring(client.get_page(sitemap).content)
        except (SourceError, ET.ParseError):
            continue
        for loc in root.iter():
            if not loc.tag.endswith("loc") or not loc.text:
                continue
            url = join_url(site, loc.text.strip())
            if url is None:
                continue
            if url.endswith(".xml") or "sitemap" in url.rsplit("/", 1)[-1]:
                if any(w in url.lower() for w in ("job", "stelle", "karriere", "career")):
                    queue.insert(0, url)
                elif len(queue) < 5:
                    queue.append(url)
            elif JOB_PATH.search(urlsplit(url).path):
                urls.append(url)
                if len(urls) >= limit:
                    return urls
    return urls


class JsonLdCareers:
    """Reads a company's careers page, its posting pages and sitemap posting URLs."""

    type = "jsonld"
    label = "Karriereseite (JSON-LD)"

    def fetch(
        self,
        client: PoliteClient,
        careers_url: str,
        company: str,
        known: set[str],
        listed: set[str] | None = None,
    ) -> list[JobPosting]:
        """Postings on the careers page; known pages are not fetched again.

        Known pages still linked from the careers page are added to `listed`.
        """
        page = client.get_page(careers_url)
        postings = {
            p.external_id: p
            for p in (parse_posting(o, careers_url, company) for o in job_postings(page.text))
        }
        candidates = job_links(page.text, str(page.url))
        if not candidates:
            candidates = sitemap_job_urls(client, careers_url)
        fetched = 0
        for url in candidates:
            if url in known:
                if listed is not None:
                    listed.add(url)
                continue
            if url in postings:
                continue
            if fetched >= MAX_JOB_PAGES:
                break
            fetched += 1
            try:
                html = client.get_page(url).text
            except SourceError:
                continue
            for obj in job_postings(html):
                posting = parse_posting(obj, url, company)
                postings[posting.external_id] = posting
        return list(postings.values())
