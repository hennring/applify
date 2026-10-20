from applify.schemas.profile import (
    Contact,
    CvSuggestion,
    Education,
    Language,
    ProfileData,
    Skill,
    Station,
    SuggestedSkill,
)
from applify.services.profile_diff import apply_changes, compute_changes

SUGGESTION = CvSuggestion(
    contact=Contact(name="Lena Beispiel", email="lena@example.org", phone="", address=""),
    roles=["Fullstack Developer", "Frontend Developer"],
    skills=[
        SuggestedSkill(name="Vue", canonical=True, category="frontend", evidence="Vue 3"),
        SuggestedSkill(name="Python", canonical=True, category="language", evidence="Python"),
    ],
    languages=[
        Language(language="Englisch", level="C1"),
        Language(language="Deutsch", level="native"),
    ],
    experience=[Station(employer="Pixelwerk GmbH", role="Dev", start="2023-04", current=True)],
    education=[Education(institution="Uni Leipzig", degree="B.Sc.", start="2018-10")],
    seniority_years=3.6,
)


def ids(profile: ProfileData) -> set[str]:
    return {c.id for c in compute_changes(profile, SUGGESTION)}


def test_empty_profile_gets_everything_as_additions() -> None:
    changes = compute_changes(ProfileData(), SUGGESTION)
    assert {c.kind for c in changes} == {"add"}
    assert ids(ProfileData()) == {
        "contact:name",
        "contact:email",
        "seniority_years",
        "role:fullstack developer",
        "role:frontend developer",
        "skill:vue",
        "skill:python",
        "language:englisch",
        "language:deutsch",
        "experience:pixelwerk gmbh|2023-04",
        "education:uni leipzig|2018-10",
    }


def test_existing_entries_are_not_proposed_again() -> None:
    profile = ProfileData(
        contact=Contact(name="Lena Beispiel", email="lena@example.org"),
        roles=["fullstack developer"],
        skills=[Skill(name="Vue", weight="must")],
        languages=[Language(language="Deutsch", level="native")],
        experience=[Station(employer="Pixelwerk GmbH", role="Developer", start="2023-04")],
        seniority_years=3.6,
    )
    assert ids(profile) == {
        "role:frontend developer",
        "skill:python",
        "language:englisch",
        "education:uni leipzig|2018-10",
    }


def test_changed_values_are_changes_with_current_value() -> None:
    profile = ProfileData(
        contact=Contact(email="alt@example.org"),
        languages=[Language(language="Englisch", level="B2")],
    )
    by_id = {c.id: c for c in compute_changes(profile, SUGGESTION)}
    assert by_id["contact:email"].kind == "change"
    assert by_id["contact:email"].current == "alt@example.org"
    assert by_id["language:englisch"].current == "B2"
    assert by_id["language:englisch"].suggested == "C1"


def test_apply_selected_changes_only() -> None:
    profile = ProfileData(
        skills=[Skill(name="React", weight="must", source="user")],
        languages=[Language(language="Englisch", level="B2")],
    )
    updated = apply_changes(
        profile, SUGGESTION, {"skill:vue", "language:englisch", "contact:email", "unknown"}
    )
    assert [(s.name, s.weight, s.source) for s in updated.skills] == [
        ("React", "must", "user"),
        ("Vue", "nice", "cv"),
    ]
    assert updated.languages == [Language(language="Englisch", level="C1")]
    assert updated.contact.email == "lena@example.org"
    assert updated.contact.name == ""
    # The original is untouched.
    assert len(profile.skills) == 1


def test_apply_everything_leaves_no_changes() -> None:
    profile = apply_changes(ProfileData(), SUGGESTION, ids(ProfileData()))
    assert compute_changes(profile, SUGGESTION) == []
    assert profile.seniority_years == 3.6
