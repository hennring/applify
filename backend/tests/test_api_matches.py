from fastapi.testclient import TestClient

from applify.sources.base import JobPosting
from tests.conftest import FakeSource

PROFILE = {
    "roles": ["Fullstack Entwickler"],
    "skills": [{"name": "Python", "weight": "must"}, {"name": "Vue", "weight": "nice"}],
    "locations": [{"name": "Leipzig", "radius_km": 30}],
    "exclude_keywords": ["Zeitarbeit"],
}


def posting(external_id: str, title: str, location: str = "04109 Leipzig") -> JobPosting:
    return JobPosting(
        source="ba",
        external_id=external_id,
        url=f"https://example.org/{external_id}",
        title=title,
        company=f"Firma {external_id}",
        location_raw=location,
    )


def run_with(api: TestClient, fake_source: FakeSource, texts: dict[str, str]) -> None:
    fake_source.texts = texts
    fake_source.postings = {
        "Fullstack Entwickler": [
            posting("1", "Fullstack Entwickler"),
            posting("2", "Projektmanager"),
            posting("3", "Fullstack Entwickler Zeitarbeit"),
            posting("4", "Fullstack Entwickler Vue", "04416 Markkleeberg"),
        ]
    }
    api.put("/api/profile", json=PROFILE)
    api.post("/api/runs")


def test_run_creates_ranked_matches(api: TestClient, fake_source: FakeSource) -> None:
    run_with(
        api,
        fake_source,
        {
            "1": "Wir arbeiten mit Python und Vue in einem kleinen Team. " * 5,
            "2": "Planung und Steuerung von Bauprojekten im Team. " * 5,
            "3": "Python und Vue bei unserem Kunden. " * 8,
        },
    )
    page = api.get("/api/matches").json()
    assert [m["job"]["title"] for m in page["items"]] == [
        "Fullstack Entwickler",
        "Fullstack Entwickler Vue",
        "Projektmanager",
    ]
    assert (page["total"], page["new"], page["excluded"]) == (3, 3, 1)
    top = page["items"][0]
    assert top["status"] == "new"
    assert top["score"] > page["items"][2]["score"]
    assert {c["key"] for c in top["breakdown"]["components"]} == {
        "skills",
        "role",
        "seniority",
        "location",
        "salary",
    }
    # Job 4 got no text: short info with a low-data marker.
    assert page["items"][1]["breakdown"]["low_data"]

    hidden = api.get("/api/matches", params={"excluded": True}).json()
    assert [m["excluded_reason"] for m in hidden["items"]] == ["Ausschlusswort „Zeitarbeit“"]


def test_seen_and_only_new(api: TestClient, fake_source: FakeSource) -> None:
    run_with(api, fake_source, {})
    first = api.get("/api/matches").json()["items"][0]["job"]["id"]

    seen = api.post(f"/api/matches/{first}/seen").json()
    assert seen["status"] == "seen"
    assert seen["seen_at"] is not None
    new = api.get("/api/matches", params={"only_new": True}).json()
    assert first not in [m["job"]["id"] for m in new["items"]]
    assert new["new"] == 2

    # F10: another run does not make the job new again.
    api.post("/api/runs")
    assert api.get(f"/api/matches/{first}").json()["status"] == "seen"

    assert api.post("/api/matches/seen").status_code == 204
    assert api.get("/api/matches").json()["new"] == 0


def test_pasted_text_rescores(api: TestClient, fake_source: FakeSource) -> None:
    run_with(api, fake_source, {})
    job_id = next(
        m["job"]["id"]
        for m in api.get("/api/matches").json()["items"]
        if m["job"]["title"] == "Projektmanager"
    )
    before = api.get(f"/api/matches/{job_id}").json()
    assert before["breakdown"]["low_data"]

    text = "Du entwickelst mit Python und Vue unsere Plattform weiter. " * 5
    after = api.put(f"/api/matches/{job_id}/text", json={"text": text}).json()
    assert after["job"]["has_full_text"]
    assert after["job"]["description"] == text.strip()
    assert not after["breakdown"]["low_data"]
    assert after["score"] > before["score"]

    too_short = api.put(f"/api/matches/{job_id}/text", json={"text": "kurz"})
    assert too_short.status_code == 422


def test_profile_change_rescores(api: TestClient, fake_source: FakeSource) -> None:
    run_with(api, fake_source, {"1": "Python und Vue. " * 20})
    assert api.get("/api/matches").json()["excluded"] == 1

    api.put("/api/profile", json=PROFILE | {"exclude_keywords": []})
    page = api.get("/api/matches").json()
    assert page["excluded"] == 0
    assert page["total"] == 4


def test_sort_by_date(api: TestClient, fake_source: FakeSource) -> None:
    run_with(api, fake_source, {})
    by_date = api.get("/api/matches", params={"sort": "date"}).json()["items"]
    assert len(by_date) == 3


def test_min_score_and_town_size(api: TestClient, fake_source: FakeSource) -> None:
    run_with(api, fake_source, {})
    scores = [m["score"] for m in api.get("/api/matches").json()["items"]]
    threshold = sorted(scores)[1]
    page = api.get("/api/matches", params={"min_score": threshold}).json()
    assert page["total"] == len([s for s in scores if s >= threshold]) < len(scores)

    small = api.get("/api/matches", params={"max_population": 100_000}).json()
    assert [m["job"]["location_raw"] for m in small["items"]] == ["04416 Markkleeberg"]
    assert small["items"][0]["job"]["population"] < 100_000


def test_unknown_match(api: TestClient) -> None:
    assert api.get("/api/matches/999").status_code == 404
    assert api.post("/api/matches/999/seen").status_code == 404
