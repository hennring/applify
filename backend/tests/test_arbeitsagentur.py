import json
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest

from applify.sources.arbeitsagentur import ArbeitsagenturSource, parse_posting
from applify.sources.base import SearchQuery, SourceError
from applify.sources.http import PoliteClient
from tests.conftest import FIXTURES

SEARCH = json.loads((FIXTURES / "ba" / "search.json").read_text(encoding="utf-8"))
DETAIL = json.loads((FIXTURES / "ba" / "detail.json").read_text(encoding="utf-8"))


def source_with(handler: Any) -> tuple[ArbeitsagenturSource, list[httpx.Request]]:
    requests: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return handler(request)  # type: ignore[no-any-return]

    client = PoliteClient(
        interval=0, transport=httpx.MockTransport(record), contact="me@example.org"
    )
    return ArbeitsagenturSource(client), requests


def test_remote_search_covers_germany_with_full_home_office() -> None:
    source, requests = source_with(lambda _: httpx.Response(200, json=SEARCH))
    source.search(SearchQuery("Java Entwickler", None, 0, remote=True))

    params = requests[0].url.params
    assert params["homeoffice"] == "prozentual_100"
    assert "wo" not in params and "umkreis" not in params


def test_radius_is_capped_at_what_the_api_accepts() -> None:
    source, requests = source_with(lambda _: httpx.Response(200, json=SEARCH))
    source.search(SearchQuery("Java Entwickler", "Leipzig", 300))
    assert requests[0].url.params["umkreis"] == "200"


def test_search_maps_postings() -> None:
    source, requests = source_with(lambda _: httpx.Response(200, json=SEARCH))
    postings = source.search(SearchQuery("Fullstack Entwickler", "Leipzig", 30))

    params = requests[0].url.params
    assert requests[0].url.path == "/jobboerse/jobsuche-service/pc/v6/jobs"
    assert (params["was"], params["wo"], params["umkreis"]) == (
        "Fullstack Entwickler",
        "Leipzig",
        "30",
    )
    assert params["angebotsart"] == "1"
    assert requests[0].headers["X-API-Key"] == "jobboerse-jobsuche"
    assert "me@example.org" in requests[0].headers["User-Agent"]

    assert [p.external_id for p in postings] == [
        "13644-312454-S",
        "11956-3065011791324001-S",
        "10001-1003809672-S",
    ]
    mgm = postings[1]
    assert mgm.source == "ba"
    assert mgm.url == "https://www.arbeitsagentur.de/jobsuche/jobdetail/11956-3065011791324001-S"
    assert mgm.company == "mgm technology partners GmbH"
    assert mgm.location_raw == "04109 Leipzig"
    assert (mgm.lat, mgm.lon) == (51.3390296, 12.3665008)
    assert (mgm.salary_min, mgm.salary_max) == (46000, 100000)
    assert mgm.remote_type == "hybrid"
    assert mgm.posted_at == datetime(2026, 10, 7, tzinfo=UTC)
    # Search results carry no text: short info until completed.
    assert not mgm.has_full_text


def test_search_without_location_and_paging() -> None:
    full_page = {"ergebnisliste": [SEARCH["ergebnisliste"][0]] * 100, "maxErgebnisse": 150}
    pages = iter([full_page, {"ergebnisliste": SEARCH["ergebnisliste"][1:], "maxErgebnisse": 150}])
    source, requests = source_with(lambda _: httpx.Response(200, json=next(pages)))
    postings = source.search(SearchQuery("Python", None, 0))
    assert len(requests) == 2
    assert "wo" not in requests[0].url.params
    assert requests[1].url.params["page"] == "2"
    assert len(postings) == 102


def test_complete_fetches_full_text() -> None:
    summary = parse_posting(SEARCH["ergebnisliste"][2])
    source, requests = source_with(lambda _: httpx.Response(200, json=DETAIL))
    full = source.complete(summary)
    # The reference number is base64 encoded in the path.
    assert requests[0].url.path.endswith("/pc/v4/jobdetails/MTAwMDEtMTAwMzgwOTY3Mi1T")
    assert full.has_full_text
    assert full.description.startswith("# IT mit Leidenschaft")
    assert "stellenangebotsBeschreibung" not in full.raw
    # The location matching the query stays, not the first of the detail's list.
    assert full.location_raw == "04109 Leipzig"


@pytest.mark.parametrize("status", [403, 404, 500])
def test_complete_keeps_short_info_on_error(status: int) -> None:
    summary = parse_posting(SEARCH["ergebnisliste"][0])
    source, _ = source_with(lambda _: httpx.Response(status))
    assert source.complete(summary) is summary


def test_search_error_is_a_source_error() -> None:
    source, _ = source_with(lambda _: httpx.Response(403, text="."))
    with pytest.raises(SourceError, match="HTTP 403"):
        source.search(SearchQuery("Python", "Leipzig", 30))


def test_salary_variants() -> None:
    base = SEARCH["ergebnisliste"][0]
    fixed = parse_posting(base | {"verguetungsangabe": "JAHRESGEHALT", "festgehalt": 60000.0})
    monthly = parse_posting(
        base
        | {"verguetungsangabe": "MONATSGEHALT", "gehaltsspanneVon": 4000, "gehaltsspanneBis": 5000}
    )
    hourly = parse_posting(base | {"verguetungsangabe": "STUNDENLOHN", "festgehalt": 18.39})
    full_remote = parse_posting(base | {"homeofficemoeglich": True, "homeofficeprozent": 100})
    assert (fixed.salary_min, fixed.salary_max) == (60000, 60000)
    assert (monthly.salary_min, monthly.salary_max) == (48000, 60000)
    assert (hourly.salary_min, hourly.salary_max) == (None, None)
    assert full_remote.remote_type == "remote"
