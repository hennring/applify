"""LLM fallback of the feature extraction (§5.8, D22): fills what the rules left open."""

import re
from typing import Literal

from applify.services.skills import SkillTaxonomy
from pydantic import BaseModel, Field

from applify_analytics.features import rules
from applify_analytics.features.extract import PROMPT_FILE, PROMPT_VERSION, Features

__all__ = ["PROMPT_VERSION", "LlmJobFeatures", "apply", "prompt_for", "system_prompt"]
# Enough for nearly every posting; the context of qwen3 is set to 8192 tokens.
MAX_TEXT_CHARS = 8000

FamilyKey = Literal[
    "fullstack", "frontend", "backend", "mobile", "data", "devops", "embedded", "sap", "qa",
    "security", "it_ops", "management", "design", "consulting", "software", "other",
]  # fmt: skip


class LlmSalary(BaseModel):
    currency: Literal["EUR", "USD", "GBP", "CHF", "other"]
    period: Literal["year", "month", "hour"]
    amount_min: float | None = None
    amount_max: float | None = None


class LlmJobFeatures(BaseModel):
    role_family: FamilyKey
    seniority: Literal["student", "junior", "mid", "senior", "lead"] | None = None
    years_min: int | None = Field(default=None, ge=0, le=rules.MAX_YEARS)
    years_max: int | None = Field(default=None, ge=0, le=rules.MAX_YEARS)
    salary: LlmSalary | None = None
    degrees: list[Literal["university", "vocational", "phd"]] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list, max_length=60)


def prompt_for(title: str, description: str) -> str:
    return f"Title: {title}\n\nPosting:\n{description[:MAX_TEXT_CHARS]}"


def system_prompt() -> str:
    return PROMPT_FILE.read_text(encoding="utf-8")


CANDIDATE = re.compile(r"^[\w.+#/ -]{2,40}$")


def apply(features: Features, result: LlmJobFeatures, taxonomy: SkillTaxonomy) -> None:
    """Fill the features the rules left open; rules always win."""
    if features.role_family is None:
        features.role_family = result.role_family
        features.origin["role_family"] = "llm"
    if features.years_min is None and result.years_min is not None:
        high = result.years_max
        features.years_min = result.years_min
        features.years_max = high if high is not None and high >= result.years_min else None
        features.origin["years"] = "llm"
    if features.seniority is None:
        level = result.seniority or rules.seniority("", features.years_min)
        if level is not None:
            features.seniority = level
            features.origin["seniority"] = "llm"
    if "salary" not in features.origin and result.salary is not None:
        _apply_salary(features, result.salary)
    if not features.degrees and result.degrees:
        features.degrees = [d for d in rules.DEGREES if d in result.degrees]
        features.origin["degrees"] = "llm"
    _apply_technologies(features, result.technologies, taxonomy)


def _apply_salary(features: Features, salary: LlmSalary) -> None:
    amounts = [a for a in (salary.amount_min, salary.amount_max) if a is not None and a > 0]
    if not amounts:
        return
    low, high = min(amounts), max(amounts)
    parsed = rules.Salary(salary.currency, salary.period, low, high if high != low else None)
    features.salary_currency, features.salary_period = salary.currency, salary.period
    features.salary_min_eur, features.salary_max_eur = rules.yearly_eur(parsed)
    features.origin["salary"] = "llm"


def _apply_technologies(
    features: Features, technologies: list[str], taxonomy: SkillTaxonomy
) -> None:
    """Known skills the patterns missed join the skills; unknown ones become candidates."""
    known = {name.casefold() for name in features.skills}
    candidates: dict[str, str] = {}
    for raw in technologies:
        name = raw.strip()
        if not CANDIDATE.match(name):
            continue
        skill = taxonomy.lookup(name)
        if skill is not None:
            if skill.name.casefold() not in known:
                features.skills.append(skill.name)
                known.add(skill.name.casefold())
        else:
            candidates.setdefault(name.casefold(), name)
    features.skill_candidates = sorted(candidates.values(), key=str.casefold)
