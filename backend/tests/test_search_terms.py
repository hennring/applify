from applify.schemas.profile import ProfileData, Skill
from applify.services.search_terms import derive_search_terms


def test_roles_german_variants_and_skill_combinations() -> None:
    profile = ProfileData(
        roles=["Fullstack Developer", "Frontend Developer (m/w/d)"],
        skills=[
            Skill(name="Python", weight="must"),
            Skill(name="SAP", weight="avoid"),
            Skill(name="Vue", weight="nice"),
            Skill(name="TypeScript", weight="must"),
        ],
    )
    assert derive_search_terms(profile) == [
        "Fullstack Developer",
        "Frontend Developer",
        "Fullstack Entwickler",
        "Frontend Entwickler",
        "Fullstack Python",
        "Frontend Python",
        "Fullstack TypeScript",
        "Frontend TypeScript",
    ]


def test_limit_and_dedup() -> None:
    profile = ProfileData(
        roles=["Fullstack Entwickler", "fullstack entwickler", "Softwareentwickler"],
        skills=[Skill(name="Python", weight="must")],
    )
    assert derive_search_terms(profile, limit=3) == [
        "Fullstack Entwickler",
        "Softwareentwickler",
        "Fullstack Python",
    ]


def test_without_roles_the_must_skills_are_searched() -> None:
    profile = ProfileData(skills=[Skill(name="Python", weight="must")])
    assert derive_search_terms(profile) == ["Python"]
    assert derive_search_terms(ProfileData()) == []


def test_no_combination_with_a_skill_already_in_the_role() -> None:
    profile = ProfileData(
        roles=["Java Entwickler", "Backend Entwickler"], skills=[Skill(name="Java", weight="must")]
    )
    assert derive_search_terms(profile) == ["Java Entwickler", "Backend Entwickler", "Backend Java"]
