"""Company discovery (F7a, D16): GitHub organisations and Wikidata companies near the profile
places. Both run at most weekly per place; GitHub org lookups continue over several runs.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

from applify.services.companies import CompanyRegistry
from applify.services.matching import ProfilePlace
from applify.sources.base import SourceConfig, SourceError
from applify.sources.http import PoliteClient

INTERVAL = timedelta(days=7)
GITHUB_API = "https://api.github.com"
# Org lookups per run; the unauthenticated core limit is 60 requests per hour.
GITHUB_LOOKUPS = {False: 25, True: 150}
WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
# Company classes (the subclass path P279* times out, see spike M2): business, enterprise,
# public company, company, privately held company, technology company, software company.
WIKIDATA_CLASSES = (
    "wd:Q4830453 wd:Q6881511 wd:Q891723 wd:Q783794 wd:Q1589009 wd:Q18388277 wd:Q1058914"
)
WIKIDATA_MAX_RADIUS = 50

Save = Callable[..., Any]


def _due(state: dict[str, str], key: str, now: datetime) -> bool:
    last = state.get(key)
    return last is None or datetime.fromisoformat(last) < now - INTERVAL


def _website(url: str | None) -> str | None:
    url = (url or "").strip()
    if not url or " " in url:
        return None
    url = url if url.startswith("http") else f"https://{url}"
    # Typos like "https://httt://example.de" leave a host without a domain.
    return url if "." in (urlsplit(url).hostname or "") else None


def discover_github(
    client: PoliteClient,
    registry: CompanyRegistry,
    places: list[ProfilePlace],
    config: SourceConfig,
    now: datetime,
) -> tuple[dict[str, Any], int]:
    """New companies from GitHub orgs; returns the updated config and the number added."""
    token = config.config.get("token")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    searched: dict[str, str] = dict(config.config.get("searched") or {})
    pending: list[str] = list(config.config.get("pending") or [])
    done: list[str] = list(config.config.get("done") or [])
    for place in places:
        if not _due(searched, place.name, now):
            continue
        data = client.get_json(
            f"{GITHUB_API}/search/users",
            params={"q": f'type:org location:"{place.name}"', "per_page": 100},
            headers=headers,
        )
        logins = [item["login"] for item in data.get("items") or [] if item.get("login")]
        pending += [login for login in logins if login not in done and login not in pending]
        searched[place.name] = now.isoformat()

    added = 0
    for login in list(pending[: GITHUB_LOOKUPS[bool(token)]]):
        org = client.get_json(f"{GITHUB_API}/orgs/{login}", headers=headers)
        pending.remove(login)
        done.append(login)
        website = _website(org.get("blog"))
        if website and (
            company := registry.get_or_create(org.get("name") or login, "github", website=website)
        ):
            company.hints = {**(company.hints or {}), "github": login}
            added += 1
    return {**config.config, "searched": searched, "pending": pending, "done": done[-5000:]}, added


def wikidata_query(place: ProfilePlace) -> str:
    radius = min(place.radius_km, WIKIDATA_MAX_RADIUS)
    return f"""
SELECT DISTINCT ?company ?companyLabel ?website WHERE {{
  SERVICE wikibase:around {{
    ?hq wdt:P625 ?loc .
    bd:serviceParam wikibase:center "Point({place.lon} {place.lat})"^^geo:wktLiteral .
    bd:serviceParam wikibase:radius "{radius}" .
  }}
  ?company wdt:P159 ?hq ; wdt:P856 ?website ; wdt:P31 ?class .
  VALUES ?class {{ {WIKIDATA_CLASSES} }}
  FILTER NOT EXISTS {{ ?company wdt:P576 ?dissolved }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "de,en". }}
}} LIMIT 1000"""


def discover_wikidata(
    client: PoliteClient,
    registry: CompanyRegistry,
    places: list[ProfilePlace],
    config: SourceConfig,
    now: datetime,
) -> tuple[dict[str, Any], int]:
    if not client.contact:
        raise SourceError("Wikidata verlangt eine Kontaktadresse im User-Agent (Einstellungen)")
    searched: dict[str, str] = dict(config.config.get("searched") or {})
    added = 0
    for place in places:
        if not _due(searched, place.name, now):
            continue
        data = client.get_json(
            WIKIDATA_SPARQL,
            params={"query": wikidata_query(place), "format": "json"},
            headers={"Accept": "application/sparql-results+json"},
        )
        for row in (data.get("results") or {}).get("bindings") or []:
            name = (row.get("companyLabel") or {}).get("value") or ""
            qid = (row.get("company") or {}).get("value", "").rsplit("/", 1)[-1]
            website = _website((row.get("website") or {}).get("value"))
            if not website or not name or name == qid:  # unlabelled items show their QID
                continue
            company = registry.get_or_create(name, "wikidata", website=website)
            if company is not None:
                company.hints = {**(company.hints or {}), "wikidata": qid}
                added += 1
        searched[place.name] = now.astimezone(UTC).isoformat()
    return {**config.config, "searched": searched}, added
