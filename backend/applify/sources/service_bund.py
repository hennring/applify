"""service.bund.de, jobs in the public sector, via the RSS feed of the job search (F7c).

Checked 2026-10-22: the search form answers with RSS when `jobsrss=true` is set; the term
filters, the location parameters do not, so the run prefilters by location. Items carry
employer, postal code and town only; the linked pages have no JSON-LD → short info (F8).
"""

import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from html import unescape

from applify.sources.base import JobPosting, SearchQuery, SourceError
from applify.sources.http import PoliteClient

FEED_URL = "https://www.service.bund.de/Content/DE/Stellen/Suche/Formular.html"
FIELD = re.compile(r"(Arbeitgeber|Ort|Bewerbungsfrist):\s*<strong>(.*?)</strong>", re.S)
ID = re.compile(r"/(\d+)\.html")


def parse_feed(content: bytes) -> list[JobPosting]:
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        raise SourceError(f"service.bund.de: ungültiger Feed ({exc})") from exc
    postings = []
    for item in root.iter("item"):
        link = (item.findtext("guid") or item.findtext("link") or "").split("#")[0].strip()
        if not (match := ID.search(link)):
            continue
        fields = {
            k: unescape(v).strip() for k, v in FIELD.findall(item.findtext("description") or "")
        }
        published = item.findtext("pubDate")
        title = unescape(item.findtext("title") or "").strip()
        summary = [
            f"{k}: {fields[k]}" for k in ("Arbeitgeber", "Ort", "Bewerbungsfrist") if k in fields
        ]
        postings.append(
            JobPosting(
                source="service_bund",
                external_id=match.group(1),
                url=link,
                title=title,
                company=fields.get("Arbeitgeber", ""),
                location_raw=fields.get("Ort", ""),
                description="\n".join(summary),
                posted_at=parsedate_to_datetime(published) if published else None,
                raw={"deadline": fields.get("Bewerbungsfrist")},
            )
        )
    return postings


class ServiceBundSource:
    name = "service_bund"
    label = "service.bund.de"
    located = False

    def __init__(self, client: PoliteClient) -> None:
        self.client = client

    def search(self, query: SearchQuery) -> list[JobPosting]:
        response = self.client.get_ok(
            FEED_URL,
            params={
                "nn": "4642046",
                "resultsPerPage": 100,
                "templateQueryString": query.term,
                "sortOrder": "dateOfIssue_dt desc",
                "jobsrss": "true",
            },
        )
        return parse_feed(response.content)

    def complete(self, posting: JobPosting) -> JobPosting:
        return posting
