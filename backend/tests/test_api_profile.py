from typing import Any

from fastapi.testclient import TestClient

from tests.conftest import FakeLLM
from tests.test_api_documents import CV_PDF, LLM_RESULT, upload

FULL_PROFILE: dict[str, Any] = {
    "roles": ["Fullstack Developer", " fullstack developer ", "Frontend Developer"],
    "seniority_years": 2.5,
    "salary_min": 50000,
    "remote_pref": "hybrid",
    "skills": [
        {"name": "vue.js", "weight": "must"},
        {"name": "Vue", "weight": "nice"},
        {"name": "Eigenes Framework", "weight": "nice", "level": "expert"},
        {"name": "SAP", "weight": "avoid"},
    ],
    "locations": [{"name": "Leipzig", "radius_km": 30}, {"name": "Berlin", "radius_km": 10}],
    "languages": [{"language": "Deutsch", "level": "native"}],
    "exclude_keywords": ["Zeitarbeit", ""],
    "exclude_companies": [],
    "preferred_companies": ["Pixelwerk"],
    "tone": "freundlich, direkt",
    "cover_letter_bullets": ["Ich arbeite gern im Team"],
    "contact": {"name": "Lena", "email": "lena@example.org", "phone": "", "address": ""},
    "experience": [{"employer": "Pixelwerk", "role": "Dev", "start": "2023-04", "current": True}],
    "education": [],
}


def test_empty_profile(api: TestClient) -> None:
    profile = api.get("/api/profile").json()
    assert profile["roles"] == []
    assert profile["remote_pref"] == "hybrid"


def test_put_profile_normalizes_and_persists(api: TestClient) -> None:
    saved = api.put("/api/profile", json=FULL_PROFILE).json()
    assert saved == api.get("/api/profile").json()
    assert saved["roles"] == ["Fullstack Developer", "Frontend Developer"]
    assert [(s["name"], s["weight"], s["canonical"]) for s in saved["skills"]] == [
        ("Vue", "must", True),
        ("Eigenes Framework", "nice", False),
        ("SAP", "avoid", False),
    ]
    assert saved["exclude_keywords"] == ["Zeitarbeit"]
    assert saved["locations"] == FULL_PROFILE["locations"]
    assert saved["experience"][0]["kind"] == "employment"


def test_put_profile_replaces_lists(api: TestClient) -> None:
    api.put("/api/profile", json=FULL_PROFILE)
    smaller = {**FULL_PROFILE, "skills": [{"name": "Python"}], "locations": []}
    saved = api.put("/api/profile", json=smaller).json()
    assert [s["name"] for s in saved["skills"]] == ["Python"]
    assert saved["locations"] == []


def test_invalid_profile_is_rejected(api: TestClient) -> None:
    bad = {**FULL_PROFILE, "languages": [{"language": "Englisch", "level": "gut"}]}
    assert api.put("/api/profile", json=bad).status_code == 422


def test_no_cv_changes_without_extracted_cv(api: TestClient) -> None:
    assert api.get("/api/profile/cv-changes").json() is None


def test_cv_changes_and_apply(api: TestClient, fake_llm: FakeLLM) -> None:
    fake_llm.result = LLM_RESULT
    doc = upload(api, "cv", "cv.pdf", CV_PDF)
    api.put("/api/profile", json={**FULL_PROFILE, "skills": [{"name": "Vue", "weight": "must"}]})

    changes = api.get("/api/profile/cv-changes").json()
    assert changes["document_id"] == doc["id"]
    by_id = {c["id"]: c for c in changes["changes"]}
    # Vue is already in the profile; TypeScript, Python and PostgreSQL come from the scan.
    assert "skill:vue" not in by_id
    assert {"skill:typescript", "skill:python", "skill:postgresql"} <= by_id.keys()
    assert by_id["contact:name"] == {
        "id": "contact:name",
        "field": "contact",
        "kind": "change",
        "key": "name",
        "current": "Lena",
        "suggested": "Lena Beispiel",
    }

    profile = api.post(
        "/api/profile/cv-changes/apply",
        json={"document_id": doc["id"], "change_ids": ["skill:python", "contact:name"]},
    ).json()
    assert profile["contact"]["name"] == "Lena Beispiel"
    assert [(s["name"], s["weight"], s["source"]) for s in profile["skills"]] == [
        ("Vue", "must", "user"),
        ("Python", "nice", "cv"),
    ]
    remaining = {c["id"] for c in api.get("/api/profile/cv-changes").json()["changes"]}
    assert "skill:python" not in remaining
    assert "contact:name" not in remaining


def test_cv_changes_for_unfinished_extraction(api: TestClient) -> None:
    doc = upload(api, "certificate", "z.pdf", CV_PDF)
    response = api.get("/api/profile/cv-changes", params={"document_id": doc["id"]})
    assert response.status_code == 409
