import json
import time
from typing import Any

import httpx
import pytest

from applify.db.models import Company
from applify.services.companies import domain_fits, posting_hints, registered_domain, same_company
from applify.services.detect import career_links, detect, slug_variants
from applify.services.discovery import _website
from applify.services.geo import get_gazetteer
from applify.services.matching import ProfilePlace
from applify.services.prefilter import Prefilter
from applify.sources.base import BudgetExceeded, JobPosting, SourceError
from applify.sources.jsonld import JsonLdCareers, job_links, job_postings, parse_posting
from tests.conftest import FakeWeb

POSTING = {
    "@context": "https://schema.org",
    "@type": "JobPosting",
    "title": "Fullstack Entwickler (m/w/d)",
    "identifier": {"@type": "PropertyValue", "name": "Acme", "value": "J-42"},
    "datePosted": "2026-10-20",
    "hiringOrganization": {"@type": "Organization", "name": "Acme Software GmbH"},
    "jobLocation": {
        "@type": "Place",
        "address": {
            "@type": "PostalAddress",
            "postalCode": "04109",
            "addressLocality": "Leipzig",
            "addressCountry": "DE",
        },
    },
    "baseSalary": {
        "@type": "MonetaryAmount",
        "currency": "EUR",
        "value": {
            "@type": "QuantitativeValue",
            "minValue": 4500,
            "maxValue": 5500,
            "unitText": "MONTH",
        },
    },
    "description": "<p><strong>Deine Aufgaben</strong></p><ul><li>Python</li><li>Vue</li></ul>"
    + "<p>"
    + "Wir entwickeln Software. " * 12
    + "</p>",
}


def page(*objects: Any, body: str = "") -> str:
    scripts = "".join(
        f'<script type="application/ld+json">{json.dumps(o)}</script>' for o in objects
    )
    return f"<html><head>{scripts}</head><body>{body}</body></html>"


def posting(**fields: Any) -> JobPosting:
    defaults: dict[str, Any] = {
        "source": "x",
        "external_id": "1",
        "url": "",
        "title": "Entwickler",
        "company": "Acme",
    }
    return JobPosting(**(defaults | fields))


# --- JSON-LD -------------------------------------------------------------------------------


def test_job_posting_from_json_ld() -> None:
    graph = {"@context": "https://schema.org", "@graph": [{"@type": "WebPage"}, POSTING]}
    objects = job_postings(page(graph))

    assert len(objects) == 1
    result = parse_posting(objects[0], "https://acme.de/jobs/fullstack", "Acme")
    assert (result.source, result.external_id) == ("jsonld", "J-42")
    assert result.title == "Fullstack Entwickler (m/w/d)"
    assert result.company == "Acme Software GmbH"
    assert (result.location_raw, result.country) == ("04109 Leipzig", "de")
    assert (result.salary_min, result.salary_max) == (54000, 66000)
    assert result.description.startswith("## Deine Aufgaben\n\n- Python\n- Vue")
    assert result.has_full_text
    assert result.posted_at is not None and result.posted_at.tzinfo is not None


def test_broken_json_ld_is_skipped() -> None:
    html = '<script type="application/ld+json">{not json</script>' + page(POSTING)
    assert len(job_postings(html)) == 1


def test_job_links_on_the_same_site() -> None:
    html = """
      <a href="/karriere/fullstack-entwickler-leipzig">A</a>
      <a href="https://acme.de/jobs/backend-developer-m-w-d?utm=x">B</a>
      <a href="https://other.de/jobs/frontend-developer">C</a>
      <a href="/karriere/">overview</a>
      <a href="/impressum">D</a>
    """
    assert job_links(html, "https://acme.de/karriere") == [
        "https://acme.de/karriere/fullstack-entwickler-leipzig",
        "https://acme.de/jobs/backend-developer-m-w-d?utm=x",
    ]


def test_careers_page_reads_linked_postings_once(web: FakeWeb) -> None:
    web.add(
        "https://acme.de/karriere",
        page(
            body='<a href="/karriere/fullstack-entwickler">x</a>'
            '<a href="/karriere/known-job-123">y</a>'
        ),
    )
    web.add("https://acme.de/karriere/fullstack-entwickler", page(POSTING))

    listed: set[str] = set()
    postings = JsonLdCareers().fetch(
        web.client(),
        "https://acme.de/karriere",
        "Acme",
        known={"https://acme.de/karriere/known-job-123", "https://acme.de/karriere/gone"},
        listed=listed,
    )

    assert [p.external_id for p in postings] == ["J-42"]
    assert "https://acme.de/karriere/known-job-123" not in web.urls()
    # Still linked, so still open; the other known page is gone.
    assert listed == {"https://acme.de/karriere/known-job-123"}


def test_careers_page_falls_back_to_the_sitemap(web: FakeWeb) -> None:
    web.add("https://acme.de/karriere", page(body="<p>Jobs werden per JavaScript geladen</p>"))
    web.add(
        "https://acme.de/sitemap.xml",
        b'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        b"<url><loc>https://acme.de/ueber-uns</loc></url>"
        b"<url><loc>https://acme.de/stellenangebote/fullstack-entwickler</loc></url></urlset>",
    )
    web.add("https://acme.de/stellenangebote/fullstack-entwickler", page(POSTING))

    postings = JsonLdCareers().fetch(web.client(), "https://acme.de/karriere", "Acme", set())

    assert [p.title for p in postings] == ["Fullstack Entwickler (m/w/d)"]


def test_robots_txt_is_honoured(web: FakeWeb) -> None:
    web.add("https://acme.de/robots.txt", b"User-agent: *\nDisallow: /karriere")
    with pytest.raises(Exception, match=r"robots\.txt"):
        JsonLdCareers().fetch(web.client(), "https://acme.de/karriere", "Acme", set())


# --- prefilter -----------------------------------------------------------------------------


@pytest.fixture
def leipzig() -> Prefilter:
    return Prefilter([ProfilePlace("Leipzig", 51.34, 12.37, 30)], "hybrid", get_gazetteer())


def test_prefilter_by_radius(leipzig: Prefilter) -> None:
    assert leipzig.check(posting(location_raw="04109 Leipzig")) is True
    assert leipzig.check(posting(location_raw="Taucha")) is True
    assert leipzig.check(posting(location_raw="München")) is False
    assert leipzig.check(posting(location_raw="Berlin, Leipzig")) is True
    assert leipzig.check(posting(lat=48.1, lon=11.6)) is False


def test_prefilter_unknown_and_foreign(leipzig: Prefilter) -> None:
    assert leipzig.check(posting(location_raw="Paris", country="fr")) is False
    assert leipzig.check(posting(location_raw="Amsterdam")) is None
    assert leipzig.check(posting(location_raw="")) is None


def test_prefilter_remote_only_if_wanted(leipzig: Prefilter) -> None:
    remote = posting(location_raw="Remote", remote_type="remote")
    assert leipzig.check(remote) is None
    wants_remote = Prefilter(leipzig.places, "remote", get_gazetteer())
    assert wants_remote.check(remote) is True
    assert wants_remote.check(posting(location_raw="München (Remote)")) is True
    assert (
        wants_remote.check(posting(location_raw="Remote", country="us", remote_type="remote"))
        is False
    )


def test_prefilter_without_places_keeps_germany() -> None:
    anywhere = Prefilter([], "hybrid", get_gazetteer())
    assert anywhere.check(posting(location_raw="München")) is True
    assert anywhere.check(posting(location_raw="Paris")) is None


# --- companies -----------------------------------------------------------------------------


def test_company_name_and_domain_helpers() -> None:
    assert registered_domain("karriere.example.co.uk") == "example.co.uk"
    assert registered_domain("www.chrono24.de") == "chrono24.de"
    assert domain_fits("chrono24.com", "Chrono24 GmbH")
    assert domain_fits("deutschebahn.com", "Deutsche Bahn AG")
    assert domain_fits("pixelwerk-leipzig.de", "Pixelwerk GmbH")
    assert not domain_fits("personaldienst.de", "Pixelwerk GmbH")
    assert same_company("1KOMMA5° GmbH", "1Komma5")
    assert same_company("N26", "N26 GmbH")
    assert same_company("Bosch Group", "Bosch")
    assert not same_company("Bosch", "Boschinger")


def test_posting_hints_find_ats_links_and_website() -> None:
    text = (
        "Bewirb dich unter https://pixelwerk.jobs.personio.de/job/1 oder per Mail an "
        "jobs@pixelwerk.de. Mehr auf www.pixelwerk.de/team. Gefunden auf www.stepstone.de"
    )
    urls, website = posting_hints(posting(company="Pixelwerk GmbH", description=text))

    assert urls == ["https://pixelwerk.jobs.personio.de/job/1", "https://www.pixelwerk.de/team"]
    assert website == "https://www.pixelwerk.de"


# --- detection -----------------------------------------------------------------------------


def company(**fields: Any) -> Company:
    defaults: dict[str, Any] = {"name": "Acme GmbH", "name_norm": "acme", "hints": {}}
    return Company(**(defaults | fields))


def test_detect_from_a_posting_link(web: FakeWeb) -> None:
    found = detect(web.client(), company(hints={"urls": ["https://acme.jobs.personio.de/job/7"]}))
    assert (found.ats_type, found.ats_token) == ("personio", "acme")
    assert web.requests == []


def test_detect_follows_the_career_link_on_the_homepage(web: FakeWeb) -> None:
    web.add("https://acme.de", page(body='<a href="/unternehmen/karriere">Karriere</a>'))
    web.add(
        "https://acme.de/unternehmen/karriere",
        page(body='<iframe src="https://boards.greenhouse.io/embed/job_board?for=acme"></iframe>'),
    )

    found = detect(web.client(), company(website="https://acme.de"))

    assert (found.ats_type, found.ats_token) == ("greenhouse", "acme")
    assert found.careers_url == "https://acme.de/unternehmen/karriere"


def test_detect_json_ld_on_a_posting_page(web: FakeWeb) -> None:
    web.add("https://acme.de", page(body='<a href="/jobs">Jobs</a>'))
    web.add("https://acme.de/jobs", page(body='<a href="/jobs/fullstack-entwickler">x</a>'))
    web.add("https://acme.de/jobs/fullstack-entwickler", page(POSTING))

    found = detect(web.client(), company(website="https://acme.de"))

    assert (found.ats_type, found.careers_url) == ("jsonld", "https://acme.de/jobs")


def test_detect_guesses_board_tokens_and_verifies_the_name(web: FakeWeb) -> None:
    web.add("https://boards-api.greenhouse.io/v1/boards/acme", {"name": "Acme"})
    web.add("https://boards-api.greenhouse.io/v1/boards/other", {"name": "Someone Else"})

    assert (detect(web.client(), company()).ats_type) == "greenhouse"
    other = company(name="Other GmbH", name_norm="other")
    assert detect(web.client(), other).ats_type == "unknown"
    assert slug_variants(company(name="Deutsche Bahn AG", website="https://www.db.de")) == [
        "deutschebahn",
        "deutsche-bahn",
    ]


def test_detect_survives_a_broken_website(web: FakeWeb) -> None:
    # A typo in a GitHub profile; once ended the whole run with httpx.InvalidURL.
    broken = company(name="VR Bits", name_norm="vr bits", website="https://httt://www.vr-bits.de")
    assert slug_variants(broken) == ["vrbits", "vr-bits"]
    assert detect(web.client(), broken).ats_type == "unknown"
    with pytest.raises(SourceError, match="ungültige URL"):
        web.client().get_ok("https://httt:.jobs.personio.de/xml")
    # Discovery no longer stores such websites.
    assert _website("https://httt://www.vr-bits.de") is None
    assert _website("vr-bits.de") == "https://vr-bits.de"


def test_detect_reports_unreachable_websites(web: FakeWeb) -> None:
    found = detect(web.client(), company(website="https://acme.de"), guess=False)
    assert found.ats_type == "unknown"
    assert found.error and "404" in found.error


# --- time budget ---------------------------------------------------------------------------


def test_budget_ends_requests_without_remembering_robots(web: FakeWeb) -> None:
    web.add("https://acme.de/robots.txt", "User-agent: *\nDisallow: /")
    client = web.client()

    with client.budget(0), pytest.raises(BudgetExceeded):
        client.get_page("https://acme.de/jobs")

    assert client.budget_exceeded and web.requests == []
    with pytest.raises(SourceError, match=r"robots\.txt"):
        client.get_page("https://acme.de/jobs")


def test_budget_shortens_the_timeout(web: FakeWeb) -> None:
    web.add("https://acme.de/jobs", "x")
    client = web.client()

    with client.budget(5):
        client.get_ok("https://acme.de/jobs")
    assert web.requests[0].extensions["timeout"]["read"] <= 5
    assert web.requests[0].extensions["timeout"]["connect"] <= 5

    client.get_ok("https://acme.de/jobs")
    assert web.requests[1].extensions["timeout"]["read"] == client.timeout


def test_timeout_at_the_end_of_the_budget_is_no_site_error(web: FakeWeb) -> None:
    def slow(request: httpx.Request) -> httpx.Response:
        time.sleep(0.02)
        raise httpx.ReadTimeout("slow", request=request)

    web.pages["https://acme.de/jobs"] = slow
    client = web.client()

    with client.budget(0.01), pytest.raises(BudgetExceeded):
        client.get_ok("https://acme.de/jobs")


def test_json_ld_keeps_what_it_read_before_the_budget_ran_out(web: FakeWeb) -> None:
    def slow(request: httpx.Request) -> httpx.Response:
        time.sleep(0.25)
        return httpx.Response(200, text=page(POSTING))

    web.add(
        "https://acme.de/jobs",
        page(
            body='<a href="/jobs/first-job">a</a><a href="/jobs/second-job">b</a>'
            '<a href="/jobs/third-job">c</a>'
        ),
    )
    web.pages["https://acme.de/jobs/first-job"] = slow
    client = web.client()
    listed: set[str] = set()

    with client.budget(0.2):
        postings = JsonLdCareers().fetch(
            client, "https://acme.de/jobs", "Acme", {"https://acme.de/jobs/third-job"}, listed
        )

    assert len(postings) == 1 and client.budget_exceeded
    assert "https://acme.de/jobs/second-job" not in web.urls()
    assert listed == {"https://acme.de/jobs/third-job"}


def test_career_links() -> None:
    html = """
      <a href="/karriere">Karriere</a><a href="/about">Über uns</a>
      <a href="https://acme.jobs.personio.de">Offene Stellen</a>
      <a href="/team"><span>Jobs</span></a><a href="https://twitter.com/acme/jobs">X</a>
    """
    assert career_links(html, "https://www.acme.de/") == [
        "https://www.acme.de/karriere",
        "https://acme.jobs.personio.de",
        "https://www.acme.de/team",
    ]
