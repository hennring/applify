from dataclasses import replace
from typing import Any

import pytest

from applify.schemas.profile import Language, ProfileData, Skill
from applify.services.matching import (
    JobFacts,
    MatchResult,
    ProfilePlace,
    match_job,
    required_languages,
    role_tokens,
)
from applify.services.skills import get_taxonomy

LEIPZIG = ProfilePlace("Leipzig", 51.3396, 12.3713, 30)
PROFILE = ProfileData(
    roles=["Fullstack Developer", "Frontend Entwickler"],
    seniority_years=2.5,
    salary_min=50000,
    remote_pref="hybrid",
    skills=[
        Skill(name="Python", weight="must"),
        Skill(name="Vue", weight="must"),
        Skill(name="TypeScript", weight="nice"),
        Skill(name="SAP", weight="avoid"),
    ],
    languages=[
        Language(language="Deutsch", level="native"),
        Language(language="Englisch", level="B2"),
    ],
    exclude_keywords=["Zeitarbeit"],
    exclude_companies=["Böse Firma"],
)
TEXT = "Wir suchen Verstärkung für unser Team. Du arbeitest mit Python, Vue und TypeScript. " * 3
JOB = JobFacts(
    title="Fullstack Entwickler (m/w/d)",
    company="Pixelwerk GmbH",
    description=TEXT,
    skills=("Python", "Vue", "TypeScript"),
    # 5 km from Leipzig's centre
    lat=51.3396,
    lon=12.4430,
    remote_type="hybrid",
    salary_min=52000,
    salary_max=62000,
    has_full_text=True,
)


def match(job: JobFacts = JOB, profile: ProfileData = PROFILE, **changes: Any) -> MatchResult:
    return match_job(replace(job, **changes), profile, [LEIPZIG], get_taxonomy())


def values(result: MatchResult) -> dict[str, float | None]:
    return {c.key: c.value for c in result.components}


def test_good_match_scores_high_with_explanation() -> None:
    result = match()
    assert result.excluded_reason is None
    assert result.score >= 90
    breakdown = result.breakdown()
    skills = next(c for c in breakdown["components"] if c["key"] == "skills")
    assert {"kind": "hit", "text": "Python (Pflicht)"} in skills["evidence"]
    # Points of the known components add up to the score.
    points = [c["points"] for c in breakdown["components"] if c["points"] is not None]
    assert sum(points) == pytest.approx(result.score, abs=1)


def test_scoring_is_deterministic() -> None:
    assert match().breakdown() == match().breakdown()


def test_unknown_components_are_neutral() -> None:
    """F13: unknown salary is taken out of the weighting, not counted as zero."""
    known = match()
    unknown = match(salary_min=None, salary_max=None)
    assert values(unknown)["salary"] is None
    assert unknown.score == known.score
    salary = next(c for c in unknown.breakdown()["components"] if c["key"] == "salary")
    assert salary["evidence"] == [{"kind": "unknown", "text": "Gehalt unbekannt"}]


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"description": TEXT + " Wir sind eine Zeitarbeitsfirma."}, "Ausschlusswort „Zeitarbeit“"),
        ({"company": "Böse Firma GmbH"}, "Ausgeschlossene Firma „Böse Firma“"),
        # Dresden is about 100 km away.
        ({"lat": 51.0509, "lon": 13.7383}, "Außerhalb aller Radien (101 km bis Leipzig)"),
        ({"salary_min": 40000, "salary_max": 45000}, "Gehalt bis 45.000 € unter 50.000 €"),
        ({"description": TEXT + " Verhandlungssicheres Englisch."}, "Gefordert: Englisch (C1)"),
        ({"title": "SAP Entwickler"}, "„SAP“ ist Kernanforderung (Titel)"),
    ],
)
def test_hard_filters(changes: dict[str, Any], reason: str) -> None:
    assert match(**changes).excluded_reason == reason


def test_remote_job_outside_radius_is_kept_for_remote_profile() -> None:
    far: dict[str, Any] = {"lat": 51.0509, "lon": 13.7383, "remote_type": "remote"}
    assert match(**far).excluded_reason is not None
    remote_profile = PROFILE.model_copy(update={"remote_pref": "remote"})
    result = match(profile=remote_profile, **far)
    assert result.excluded_reason is None
    assert values(result)["location"] == 1.0


def test_only_explicit_language_requirements_count() -> None:
    assert required_languages("Gute Englischkenntnisse") == {}
    assert required_languages("Englisch fließend") == {"Englisch": "B2"}
    # The level is for the language next to it, not for the one after "und".
    assert required_languages("Deutschkenntnisse (mindestens C1) und gute Englischkenntnisse") == {
        "Deutsch": "C1"
    }
    assert match(description=TEXT + " Fließende Englischkenntnisse.").excluded_reason is None


def test_skills_component() -> None:
    assert values(match())["skills"] == 1.0
    # One must skill; the target is what the profile can reach: 2 must + 0.5 nice.
    only_python = match(skills=("Python",), description="Python " * 50)
    assert values(only_python)["skills"] == pytest.approx(1 / 2.5)
    with_avoid = match(skills=("Python", "SAP"), description="Python und SAP " * 30)
    assert values(with_avoid)["skills"] == 0.0
    # Short info without recognizable skills: unknown, not zero.
    short = match(skills=(), description="", has_full_text=False)
    assert values(short)["skills"] is None
    assert short.low_data


def test_role_component() -> None:
    assert role_tokens("Full-Stack Webentwickler (m/w/d)") == {"fullstack", "web", "entwickler"}
    assert values(match(title="Fullstack Developer"))["role"] == 1.0
    assert values(match(title="Backend Entwickler"))["role"] == 0.5
    assert values(match(title="Projektmanager"))["role"] == 0.0


def test_seniority_component() -> None:
    assert values(match())["seniority"] is None
    assert values(match(title="Junior Fullstack Entwickler"))["seniority"] == 1.0
    assert values(match(title="Senior Fullstack Entwickler"))["seniority"] == 0.2
    demand = match(description=TEXT + " Mindestens 4 Jahre Berufserfahrung.")
    assert values(demand)["seniority"] == pytest.approx(0.5)


def test_location_and_salary_components() -> None:
    near = values(match())["location"]
    assert near is not None and near > 0.9
    assert values(match(lat=None, lon=None))["location"] is None
    assert values(match(salary_min=46000, salary_max=None))["salary"] == 0.5
    assert values(match(salary_min=30000, salary_max=None))["salary"] == 0.0
