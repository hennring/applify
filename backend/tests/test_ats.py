import json
from datetime import UTC, date, datetime
from typing import Any

import httpx
import pytest

from applify.sources.ats import (
    ADAPTERS,
    Feed,
    Greenhouse,
    Lever,
    Personio,
    Recruitee,
    SmartRecruiters,
    Workday,
    _posted_on,
    find_ats,
)
from tests.conftest import FIXTURES, FakeWeb

ATS = FIXTURES / "ats"


def load(name: str) -> Any:
    return json.loads((ATS / name).read_text(encoding="utf-8"))


def test_personio(web: FakeWeb) -> None:
    web.add(
        "https://chrono24.jobs.personio.de/xml",
        (ATS / "personio.xml").read_bytes(),
        headers={"ETag": '"v1"'},
    )
    feed = Feed("chrono24", "Chrono24")

    postings = Personio().fetch(web.client(), feed)

    assert feed.etag == '"v1"'
    assert len(postings) == 3
    first = postings[0]
    assert (first.source, first.external_id) == ("ats:personio", "chrono24:2735451")
    assert first.url == "https://chrono24.jobs.personio.de/job/2735451"
    assert (first.company, first.location_raw) == ("Chrono24 GmbH", "Karlsruhe")
    assert first.description.startswith("## Beschreibung\n\nChrono24 ist")
    assert first.has_full_text
    assert first.posted_at is not None and first.posted_at.tzinfo is not None
    # A position without descriptions is short info.
    assert not postings[2].has_full_text


def test_personio_falls_back_to_com(web: FakeWeb) -> None:
    web.add("https://acme.jobs.personio.com/xml", (ATS / "personio.xml").read_bytes())

    postings = Personio().fetch(web.client(), Feed("acme", "Acme"))

    assert len(postings) == 3
    assert postings[0].url.startswith("https://acme.jobs.personio.com/job/")


def test_unchanged_feed_is_skipped(web: FakeWeb) -> None:
    web.pages["https://chrono24.jobs.personio.de/xml"] = lambda request: httpx.Response(
        304 if request.headers.get("If-None-Match") == '"v1"' else 200
    )
    feed = Feed("chrono24", "Chrono24", etag='"v1"')

    assert Personio().fetch(web.client(), feed) == []
    assert feed.unchanged


def test_greenhouse(web: FakeWeb) -> None:
    data = load("greenhouse.json")
    web.add("https://boards-api.greenhouse.io/v1/boards/n26/jobs", data)

    postings = Greenhouse().fetch(web.client(), Feed("n26", "N26"))

    assert web.requests[0].url.params["content"] == "true"
    first = postings[0]
    assert (first.external_id, first.company, first.location_raw) == ("n26:8184721", "N26", "Paris")
    assert first.url.startswith("https://n26.com/")
    assert first.description.startswith("## About the opportunity")
    assert "&lt;" not in first.description


def test_lever(web: FakeWeb) -> None:
    web.add("https://api.lever.co/v0/postings/spotify", load("lever.json"))

    postings = Lever().fetch(web.client(), Feed("spotify", "Spotify"))

    paris, vietnam, new_york = postings
    assert (paris.company, paris.location_raw, paris.country) == ("Spotify", "Paris", "fr")
    assert (vietnam.remote_type, new_york.remote_type) == ("hybrid", "remote")
    assert "## What You'll Do" in paris.description
    assert paris.url == "https://jobs.lever.co/spotify/f7eb82ce-b57e-4dc0-b84a-7f7ec05bf66e"


def test_recruitee(web: FakeWeb) -> None:
    web.add("https://bunq.recruitee.com/api/offers", load("recruitee.json"))

    postings = Recruitee().fetch(web.client(), Feed("bunq", "bunq"))

    first = postings[0]
    assert (first.external_id, first.company, first.country) == ("bunq:2783543", "bunq", "nl")
    assert first.remote_type == "hybrid"
    assert first.url == "https://careers.bunq.com/o/head-of-product-6"
    assert first.has_full_text


def test_smartrecruiters_list_and_detail(web: FakeWeb) -> None:
    api = "https://api.smartrecruiters.com/v1/companies/BoschGroup/postings"
    web.add(api, load("smartrecruiters_list.json"))
    web.add(f"{api}/744000157147873", load("smartrecruiters_detail.json"))
    adapter = SmartRecruiters()
    client = web.client()

    postings = adapter.fetch(client, Feed("BoschGroup", "Bosch"))

    assert web.requests[0].url.params["country"] == "de"
    first = postings[0]
    assert (first.company, first.location_raw, first.country) == ("Bosch Group", "50858 Köln", "de")
    assert first.lat == pytest.approx(50.915306)
    assert first.remote_type == "hybrid"
    assert not first.has_full_text
    full = adapter.complete(client, first)
    assert full.has_full_text
    assert "## Qualifikationen" in full.description


def test_workday_searches_terms_and_completes(web: FakeWeb) -> None:
    api = "https://db.wd3.myworkdayjobs.com/wday/cxs/db/DBWebsite"
    listing = load("workday_list.json")
    web.add(f"{api}/jobs", listing)
    path = listing["jobPostings"][0]["externalPath"]
    web.add(f"{api}{path}", load("workday_detail.json"))
    adapter = Workday()
    client = web.client()

    postings = adapter.fetch(client, Feed("db/wd3/DBWebsite", "Deutsche Bank", ["Java", "Python"]))

    searched = [
        (json.loads(r.content)["searchText"], json.loads(r.content)["offset"]) for r in web.requests
    ]
    # Two pages per term at most (the tenant has 818 postings).
    assert searched == [("Java", 0), ("Java", 20), ("Python", 0), ("Python", 20)]
    assert len(postings) == 3  # the same postings for both terms count once
    first = postings[0]
    assert first.url == f"https://db.wd3.myworkdayjobs.com/DBWebsite{path}"
    assert first.company == "Deutsche Bank"
    full = adapter.complete(client, first)
    assert full.country == "ro"
    assert full.has_full_text


def test_posted_on() -> None:
    today = date(2026, 10, 22)
    assert _posted_on("Posted Today", today) == datetime(2026, 10, 22, tzinfo=UTC)
    assert _posted_on("Posted Yesterday", today) == datetime(2026, 10, 21, tzinfo=UTC)
    assert _posted_on("Posted 30+ Days Ago", today) == datetime(2026, 9, 22, tzinfo=UTC)
    assert _posted_on("", today) is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("https://chrono24.jobs.personio.de/job/123", ("personio", "chrono24")),
        ('<a href="https://Acme.jobs.personio.com">', ("personio", "acme")),
        ("https://boards.greenhouse.io/n26/jobs/1", ("greenhouse", "n26")),
        (
            '<script src="https://boards.greenhouse.io/embed/job_board/js?for=celonis">',
            ("greenhouse", "celonis"),
        ),
        ("https://job-boards.eu.greenhouse.io/gitlab", ("greenhouse", "gitlab")),
        ("https://jobs.lever.co/spotify/abc", ("lever", "spotify")),
        ("https://jobs.eu.lever.co/acme", ("lever", "acme")),
        ("https://bunq.recruitee.com/o/x", ("recruitee", "bunq")),
        ("https://jobs.smartrecruiters.com/BoschGroup/123", ("smartrecruiters", "BoschGroup")),
        (
            "https://db.wd3.myworkdayjobs.com/de-DE/DBWebsite/job/x",
            ("workday", "db/wd3/DBWebsite"),
        ),
        ("https://www.example.de/karriere", None),
        ("https://www.recruitee.com/", None),
    ],
)
def test_find_ats(text: str, expected: tuple[str, str] | None) -> None:
    assert find_ats(text) == expected


def test_probe_returns_the_company_name(web: FakeWeb) -> None:
    web.add("https://chrono24.jobs.personio.de/xml", (ATS / "personio.xml").read_bytes())
    web.add("https://boards-api.greenhouse.io/v1/boards/n26", {"name": "N26"})
    client = web.client()

    assert ADAPTERS["personio"].probe(client, "chrono24") == "Chrono24 GmbH"
    assert ADAPTERS["personio"].probe(client, "nobody") is None
    assert ADAPTERS["greenhouse"].probe(client, "n26") == "N26"
    assert ADAPTERS["greenhouse"].probe(client, "nobody") is None
