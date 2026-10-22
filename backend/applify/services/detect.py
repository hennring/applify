"""Find a company's careers page and its ATS (§5.1 "Erkennung"), once per company."""

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urljoin, urlsplit

from applify.db.models import Company
from applify.services.companies import registered_domain, same_company
from applify.services.normalize import normalize_company
from applify.sources.ats import ADAPTERS, PROBE_ORDER, find_ats
from applify.sources.base import SourceError
from applify.sources.http import PoliteClient
from applify.sources.jsonld import JOB_PATH, job_links, job_postings, sitemap_job_urls

ANCHOR = re.compile(r"<a\s[^>]*href\s*=\s*[\"']([^\"'#]+)[\"'][^>]*>(.*?)</a>", re.I | re.S)
CAREER_WORDS = re.compile(r"karriere|career|jobs?\b|stellen|offene positionen|join us", re.I)
TYPICAL_PATHS = ("/karriere", "/jobs", "/careers", "/stellenangebote")
MAX_CAREER_PAGES = 3


@dataclass
class Detection:
    ats_type: str = "unknown"
    ats_token: str | None = None
    careers_url: str | None = None
    error: str | None = None


def _site(url: str) -> str:
    url = url if url.startswith("http") else f"https://{url}"
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}/"


def career_links(html: str, base: str) -> list[str]:
    """Links on a homepage that lead to careers pages, same site or an ATS board."""
    host = registered_domain(urlsplit(base).netloc)
    links: dict[str, None] = {}
    for href, text in ANCHOR.findall(html):
        url = urljoin(base, href.strip())
        label = re.sub(r"<[^>]+>", " ", text)
        if not url.startswith("http"):
            continue
        if find_ats(url) or (
            registered_domain(urlsplit(url).netloc) == host
            and (CAREER_WORDS.search(urlsplit(url).path) or CAREER_WORDS.search(label))
        ):
            links[url.split("#")[0]] = None
    return list(links)


def _inspect(client: PoliteClient, url: str) -> tuple[Detection | None, str]:
    """ATS or JSON-LD on one page; returns the page text for further links."""
    page = client.get_page(url)
    final = str(page.url)
    if hit := find_ats(final) or find_ats(page.text):
        return Detection(hit[0], hit[1], final), page.text
    if job_postings(page.text):
        return Detection("jsonld", None, final), page.text
    return None, page.text


def slug_variants(company: Company) -> list[str]:
    norm = normalize_company(company.name)
    variants = [norm.replace(" ", ""), norm.replace(" ", "-")]
    if company.website:
        variants.insert(0, registered_domain(urlsplit(_site(company.website)).netloc).split(".")[0])
    return [v for v in dict.fromkeys(variants) if len(v) >= 3][:3]


def probe(client: PoliteClient, company: Company) -> Detection | None:
    """Guess board tokens from the name and keep one whose feed names the same company."""
    for slug in slug_variants(company):
        for ats_type in PROBE_ORDER:
            try:
                name = ADAPTERS[ats_type].probe(client, slug)
            except (SourceError, ValueError):
                continue
            if name and same_company(name, company.name):
                return Detection(ats_type, slug)
    return None


def detect(client: PoliteClient, company: Company, *, guess: bool = True) -> Detection:
    leads = [company.careers_url, company.website, *((company.hints or {}).get("urls") or [])]
    for url in filter(None, leads):
        if hit := find_ats(url):
            return Detection(hit[0], hit[1], url if "://" in url else None)

    errors: list[str] = []
    # Careers links from postings ("firma.de/karriere/") before the homepage.
    hinted = [
        u
        for u in (company.hints or {}).get("urls") or []
        # Overview pages only; a single posting is no careers page to read every run.
        if CAREER_WORDS.search(urlsplit(u).path) and not JOB_PATH.search(urlsplit(u).path)
    ][:2]
    pages = list(dict.fromkeys(u for u in (company.careers_url, *hinted, company.website) if u))
    seen: set[str] = set()
    for start in pages:
        start = start if start.startswith("http") else f"https://{start}"
        try:
            found, html = _inspect(client, start)
        except SourceError as exc:
            errors.append(str(exc))
            continue
        seen.add(start)
        if found:
            return found
        candidates = career_links(html, start)[:MAX_CAREER_PAGES]
        if not candidates and start == company.website:
            candidates = [urljoin(_site(start), p) for p in TYPICAL_PATHS]
        for url in candidates:
            if url in seen:
                continue
            seen.add(url)
            if hit := find_ats(url):
                return Detection(hit[0], hit[1], url)
            try:
                found, career_html = _inspect(client, url)
            except SourceError:
                continue
            if found:
                return found
            # A careers page listing postings whose pages carry JSON-LD.
            for link in job_links(career_html, url)[:1]:
                try:
                    if job_postings(client.get_page(link).text):
                        return Detection("jsonld", None, url)
                except SourceError:
                    pass
            if job_links(career_html, url):
                break

    if company.website:
        try:
            for url in sitemap_job_urls(client, _site(company.website), limit=3)[:1]:
                if job_postings(client.get_page(url).text):
                    return Detection("jsonld", None, _site(company.website))
        except SourceError as exc:
            errors.append(str(exc))

    if guess and (found := probe(client, company)):
        return found
    return Detection(error="; ".join(errors[:2]) or None)


def apply_detection(company: Company, found: Detection, now: datetime | None = None) -> None:
    company.ats_type = found.ats_type
    company.ats_token = found.ats_token
    if found.careers_url:
        company.careers_url = found.careers_url[:1000]
    company.detection_status = "done"
    company.detected_at = now or datetime.now(UTC)
    company.etag = None
    company.last_error = found.error[:500] if found.error else None
