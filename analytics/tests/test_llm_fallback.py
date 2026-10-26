from typing import get_args

from applify.services.skills import get_taxonomy

from applify_analytics.features import llm
from applify_analytics.features.extract import Features, JobInput, extract
from applify_analytics.features.rules import get_role_rules


def job(title: str, description: str = "") -> JobInput:
    return JobInput(1, title, description, True, None, None)


def test_schema_offers_exactly_the_role_families() -> None:
    assert set(get_args(llm.FamilyKey)) == {f.key for f in get_role_rules().families}


def test_rules_win_and_the_llm_fills_the_gaps() -> None:
    features = extract(
        job("Senior Java Entwickler", "Java und Kotlin. 3+ years experience"), get_taxonomy()
    )
    answer = llm.LlmJobFeatures(
        role_family="software",
        seniority="mid",
        years_min=1,
        salary=llm.LlmSalary(currency="EUR", period="month", amount_min=5000, amount_max=6000),
        degrees=["university"],
        technologies=["Java", "Spring Boot", "Snowflake", "  ", "Kotlin"],
    )
    llm.apply(features, answer, get_taxonomy())

    assert (features.role_family, features.origin["role_family"]) == ("backend", "rule")
    assert (features.seniority, features.origin["seniority"]) == ("senior", "rule")
    assert (features.years_min, features.origin["years"]) == (3, "rule")
    assert (features.salary_min_eur, features.salary_max_eur) == (60000, 72000)
    assert features.origin["salary"] == "llm"
    assert (features.degrees, features.origin["degrees"]) == (["university"], "llm")
    # Known skills the patterns missed join the skills; unknown ones are candidates.
    assert "Spring Boot" in features.skills
    assert features.skill_candidates == ["Snowflake"]


def test_seniority_from_llm_years_if_the_llm_names_no_level() -> None:
    features = extract(job("Mitarbeiter IT (m/w/d)"), get_taxonomy())
    llm.apply(features, llm.LlmJobFeatures(role_family="it_ops", years_min=6), get_taxonomy())
    assert (features.role_family, features.seniority, features.years_min) == ("it_ops", "senior", 6)
    assert features.origin == {"role_family": "llm", "years": "llm", "seniority": "llm"}


def test_foreign_salary_is_recorded_without_eur_values() -> None:
    features = Features()
    salary = llm.LlmSalary(currency="USD", period="year", amount_min=140000, amount_max=185000)
    llm.apply(features, llm.LlmJobFeatures(role_family="other", salary=salary), get_taxonomy())
    assert (features.salary_currency, features.salary_min_eur, features.salary_max_eur) == (
        "USD",
        None,
        None,
    )
