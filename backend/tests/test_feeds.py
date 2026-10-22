import json
from datetime import UTC, datetime

import httpx

from applify.sources.adzuna import AdzunaSource
from applify.sources.arbeitnow import ArbeitnowSource
from applify.sources.base import SearchQuery
from applify.sources.html_text import html_to_text
from applify.sources.service_bund import FEED_URL, ServiceBundSource, parse_feed
from tests.conftest import FIXTURES, FakeWeb

FEEDS = FIXTURES / "feeds"


def test_html_to_text_keeps_structure() -> None:
    html = (
        "<p><strong>Deine Aufgaben:</strong></p><ul><li><p>Code &amp; Tests</p></li>"
        "<li>Reviews</li></ul><p>Wir bieten <b>viel</b> Spaß.<br>Zeile 2</p>"
        "<h3>Profil</h3><script>track()</script><p>Python</p>"
    )
    assert html_to_text(html) == (
        "## Deine Aufgaben\n\n- Code & Tests\n- Reviews\n\nWir bieten viel Spaß.\n\n"
        "Zeile 2\n\n## Profil\n\nPython"
    )
    assert html_to_text("schon Text") == "schon Text"


def test_arbeitnow_reads_pages_until_the_last(web: FakeWeb) -> None:
    page = json.loads((FEEDS / "arbeitnow.json").read_text(encoding="utf-8"))
    last = {**page, "data": page["data"][:1], "links": {**page["links"], "next": None}}
    web.pages["https://www.arbeitnow.com/api/job-board-api"] = lambda request: httpx.Response(
        200, json=page if request.url.params["page"] == "1" else last
    )

    postings = ArbeitnowSource(web.client()).fetch()

    assert len(postings) == 4
    first = postings[0]
    assert first.source == "arbeitnow"
    assert first.external_id == page["data"][0]["slug"]
    assert first.company == "7NXT GmbH"
    assert first.location_raw == "Berlin"
    assert first.has_full_text
    assert first.description.startswith("## CRM Manager")
    assert first.posted_at == datetime.fromtimestamp(page["data"][0]["created_at"], UTC)


def test_adzuna_search_maps_postings_and_ignores_predicted_salaries(web: FakeWeb) -> None:
    web.add(
        "https://api.adzuna.com/v1/api/jobs/de/search/1",
        json.loads((FEEDS / "adzuna.json").read_text(encoding="utf-8")),
    )
    source = AdzunaSource(web.client(), "id", "key")

    postings = source.search(SearchQuery("Fullstack Entwickler", "Leipzig", 30))

    params = web.requests[0].url.params
    assert (params["app_id"], params["what"], params["where"], params["distance"]) == (
        "id",
        "Fullstack Entwickler",
        "Leipzig",
        "30",
    )
    first, second = postings
    assert (first.external_id, first.company, first.lat) == (
        "4711000001",
        "Pixelwerk GmbH",
        51.3397,
    )
    assert (first.salary_min, first.salary_max) == (55000, 65000)
    assert not first.has_full_text
    assert (second.salary_min, second.salary_max) == (None, None)


def test_service_bund_feed() -> None:
    postings = parse_feed((FEEDS / "service_bund.xml").read_bytes())

    assert len(postings) == 3
    first = postings[0]
    assert first.source == "service_bund"
    assert first.external_id == "6676869"
    assert first.company == "Technische Informationsbibliothek (TIB)"
    assert first.location_raw == "30167 Hannover"
    assert "#" not in first.url
    assert first.posted_at is not None and first.posted_at.tzinfo is not None
    assert not first.has_full_text
    assert postings[2].company == "Humboldt-Universität zu Berlin"


def test_service_bund_searches_by_term(web: FakeWeb) -> None:
    web.add(FEED_URL, (FEEDS / "service_bund.xml").read_bytes())
    source = ServiceBundSource(web.client())

    assert len(source.search(SearchQuery("Softwareentwickler", None, 0))) == 3
    params = web.requests[0].url.params
    assert (params["templateQueryString"], params["jobsrss"]) == ("Softwareentwickler", "true")
