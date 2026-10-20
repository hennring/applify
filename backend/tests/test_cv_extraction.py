from datetime import date
from typing import Any

import pytest

from applify.schemas.profile import Station
from applify.services.cv_extraction import (
    CvExtraction,
    classify_station,
    experience_years,
    extract_cv,
    map_language_level,
    normalize,
    parse_month,
)
from applify.services.skills import get_taxonomy
from tests.conftest import FIXTURES, FakeLLM

TODAY = date(2026, 10, 20)
CV_TEXT = (FIXTURES / "cvs" / "de_fullstack.txt").read_text(encoding="utf-8")


def run(raw: dict[str, Any], text: str = CV_TEXT) -> Any:
    return normalize(CvExtraction.model_validate(raw), text, get_taxonomy(), TODAY)


@pytest.mark.parametrize(
    ("value", "end", "expected"),
    [
        ("2021-03", False, "2021-03"),
        ("2021-3", False, "2021-03"),
        ("03/2021", False, "2021-03"),
        ("3.2021", True, "2021-03"),
        ("2021", False, "2021-01"),
        ("2021", True, "2021-12"),
        ("heute", True, None),
        ("2021-13", False, None),
        (None, False, None),
    ],
)
def test_parse_month(value: str | None, end: bool, expected: str | None) -> None:
    assert parse_month(value, end=end) == expected


@pytest.mark.parametrize(
    ("level", "expected"),
    [
        ("Muttersprache", "native"),
        ("verhandlungssicher (C1)", "C1"),
        ("B2", "B2"),
        ("sehr gute Kenntnisse", "C1"),
        ("gute Kenntnisse", "B2"),
        ("Grundkenntnisse", "A2"),
        ("fluent", "C1"),
        ("irgendwie", None),
    ],
)
def test_map_language_level(level: str, expected: str | None) -> None:
    assert map_language_level(level) == expected


@pytest.mark.parametrize(
    ("role", "kind"),
    [
        ("Fullstack Developer", "employment"),
        ("Werkstudentin Webentwicklung", "working_student"),
        ("Praktikum Softwareentwicklung", "internship"),
        ("Software Engineering Intern", "internship"),
        ("Auszubildender Fachinformatiker", "apprenticeship"),
    ],
)
def test_classify_station(role: str, kind: str) -> None:
    assert classify_station(role) == kind


def test_experience_years_merges_overlaps_and_weights_kinds() -> None:
    stations = [
        Station(employer="A", start="2023-04", current=True),  # 43 months
        Station(employer="B", kind="working_student", start="2021-10", end="2023-03"),  # 18 * .5
        Station(employer="C", kind="internship", start="2021-03", end="2021-08"),  # 0
        Station(employer="D", start="2024-01", end="2024-06"),  # overlaps A, counts once
        Station(employer="E", start=None, end="2020-01"),  # no start: ignored
    ]
    assert experience_years(stations, TODAY) == round((43 + 9) / 12, 1)


def test_experience_years_without_dates() -> None:
    assert experience_years([Station(employer="A")], TODAY) is None


def test_normalize_skills_requires_mention_and_maps_to_taxonomy() -> None:
    suggestion = run(
        {
            "skills": [
                {"name": "vue.js", "evidence": "Vue 3, Pinia"},
                {"name": "Angular", "evidence": "Vue 3, Pinia und TypeScript"},  # not in CV
                {"name": "Kubernetes", "evidence": "erfunden"},
            ]
        }
    )
    names = [s.name for s in suggestion.skills]
    assert names[0] == "Vue"
    assert suggestion.skills[0].canonical
    assert "Angular" not in names
    assert suggestion.dropped_skills == ["Angular", "Kubernetes"]


def test_normalize_adds_known_skills_the_llm_missed() -> None:
    names = {s.name for s in run({"skills": []}).skills}
    assert {"Pinia", "Node.js", "Express", "GitLab CI", "Flask", "Accessibility"} <= names


def test_unknown_skill_kept_as_free_text_if_in_text() -> None:
    suggestion = run(
        {"skills": [{"name": "Buchungsplattform", "evidence": "einer Buchungsplattform"}]}
    )
    free = [s for s in suggestion.skills if not s.canonical]
    assert [s.name for s in free] == ["Buchungsplattform"]


def test_contact_is_checked_against_text() -> None:
    suggestion = run(
        {
            "contact": {
                "name": "LENA BEISPIEL",
                "email": "lena@erfunden.de",
                "phone": "+49 341 0000000",
                "address": "Karl-Liebknecht-Straße 12, 04107 Leipzig",
            }
        }
    )
    assert suggestion.contact.name == "Lena Beispiel"
    assert suggestion.contact.email == "lena.beispiel@example.org"
    assert suggestion.contact.phone == "+49 341 1234567"


def test_roles_exclude_internships_and_are_deduplicated() -> None:
    suggestion = run(
        {
            "roles": [
                "Fullstack Developer",
                "fullstack developer",
                "Werkstudentin Webentwicklung",
                "Praktikantin",
            ]
        }
    )
    assert suggestion.roles == ["Fullstack Developer"]


def test_stations_and_years() -> None:
    suggestion = run(
        {
            "experience": [
                {
                    "employer": "Pixelwerk GmbH",
                    "role": "Fullstack Developer",
                    "start": "04/2023",
                    "current": True,
                },
                {
                    "employer": "Datenhafen AG",
                    "role": "Werkstudentin",
                    "start": "2021-10",
                    "end": "2023-03",
                },
                {"employer": " ", "role": "leer"},
            ]
        }
    )
    assert [s.employer for s in suggestion.experience] == ["Pixelwerk GmbH", "Datenhafen AG"]
    assert suggestion.experience[0].end is None
    assert suggestion.experience[1].kind == "working_student"
    assert suggestion.seniority_years == round((43 + 9) / 12, 1)


def test_extract_cv_passes_text_to_llm() -> None:
    llm = FakeLLM({"contact": {"name": "Lena Beispiel"}})
    suggestion = extract_cv(CV_TEXT, llm, get_taxonomy(), TODAY)
    assert suggestion.contact.name == "Lena Beispiel"
    assert "Pixelwerk GmbH" in llm.calls[0]
