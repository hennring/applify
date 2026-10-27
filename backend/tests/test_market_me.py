from dataclasses import replace
from datetime import date

from applify.services.market_me import GOOD_SCORE, Rated, skill_lever
from applify.services.matching import match_job
from applify.services.skills import get_taxonomy
from tests.test_matching import JOB, LEIPZIG, PROFILE

TEXT = "Wir suchen Verstärkung. Du arbeitest mit Python, Vue, TypeScript, Go und Kafka. " * 3


def rated(**changes: object) -> Rated:
    job = replace(JOB, **changes)  # type: ignore[arg-type]
    result = match_job(job, PROFILE, [LEIPZIG], get_taxonomy())
    return Rated(job, result.components, result.score, date(2026, 10, 19))


def test_skill_lever_counts_jobs_that_become_good_matches() -> None:
    jobs = [
        rated(description=TEXT, skills=("Python", "Vue", "TypeScript", "Go", "Kafka")),
        rated(description=TEXT, skills=("Python", "Go")),
        rated(description="Nur Rust.", skills=("Rust",)),
    ]
    lever = {s["skill"]: s for s in skill_lever(jobs, PROFILE, get_taxonomy())}
    assert set(lever) == {"Go", "Kafka", "Rust"}  # skills of the profile are left out
    assert lever["Go"]["jobs"] == 2
    assert lever["Go"]["avg_gain"] > 0
    # Each lever counts only jobs crossing the bound, never more than ask for the skill.
    assert all(0 <= s["new_good"] <= s["jobs"] for s in lever.values())
    below = [r for r in jobs if "Go" in r.facts.skills and r.score < GOOD_SCORE]
    assert lever["Go"]["new_good"] <= len(below)
