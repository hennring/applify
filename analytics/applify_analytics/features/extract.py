"""Features of one job from rules (§5.8): role, seniority, experience, salary, skills."""

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from applify.services.matching import required_languages
from applify.services.skills import SKILLS_FILE, SkillTaxonomy

from applify_analytics.features import rules

# Bump when the extraction code changes. Changes to roles.yaml, skills.yaml or the LLM
# prompt are picked up through their content hash, so every job is extracted again.
RULES_VERSION = 2
PROMPT_VERSION = "job_features_v2"
PROMPT_FILE = Path(__file__).resolve().parents[1] / "prompts" / f"{PROMPT_VERSION}.md"

Origin = Literal["source", "rule", "llm"]


def extractor_version() -> str:
    files = (rules.ROLES_FILE, SKILLS_FILE, PROMPT_FILE)
    digest = hashlib.sha256(b"".join(path.read_bytes() for path in files)).hexdigest()
    return f"{RULES_VERSION}-{digest[:12]}"


@dataclass(frozen=True)
class JobInput:
    job_id: int
    title: str
    description: str
    has_full_text: bool
    # Structured salary from the source (BA), yearly EUR.
    salary_min: int | None
    salary_max: int | None

    def input_hash(self) -> str:
        content = [self.title, self.description, self.salary_min, self.salary_max]
        return hashlib.sha256(json.dumps(content).encode()).hexdigest()


@dataclass
class Features:
    role_family: str | None = None
    seniority: str | None = None
    years_min: int | None = None
    years_max: int | None = None
    salary_min_eur: int | None = None
    salary_max_eur: int | None = None
    salary_currency: str | None = None
    salary_period: str | None = None
    skills: list[str] = field(default_factory=list)
    # Technologies outside the taxonomy, named by the LLM.
    skill_candidates: list[str] = field(default_factory=list)
    languages: dict[str, str] = field(default_factory=dict)
    degrees: list[str] = field(default_factory=list)
    # Per feature where its value comes from; features left out are unknown.
    origin: dict[str, Origin] = field(default_factory=dict)


def extract(job: JobInput, taxonomy: SkillTaxonomy) -> Features:
    text = job.description
    features = Features()

    if family := rules.get_role_rules().classify(job.title):
        features.role_family = family
        features.origin["role_family"] = "rule"

    years_min, years_max = rules.required_years(text)
    if years_min is not None:
        features.years_min, features.years_max = years_min, years_max
        features.origin["years"] = "rule"
    if level := rules.seniority(job.title, years_min):
        features.seniority = level
        features.origin["seniority"] = "rule"

    _salary(job, features)

    mentions = taxonomy.find_mentions(f"{job.title}\n{text}")
    features.skills = [m.skill.name for m in mentions]
    if features.skills:
        features.origin["skills"] = "rule"
    if languages := required_languages(text):
        features.languages = dict(languages)
        features.origin["languages"] = "rule"
    if found := rules.degrees(text):
        features.degrees = found
        features.origin["degrees"] = "rule"
    return features


def _salary(job: JobInput, features: Features) -> None:
    if job.salary_min is not None or job.salary_max is not None:
        structured = rules.Salary(
            "EUR",
            "year",
            float(job.salary_min if job.salary_min is not None else job.salary_max or 0),
            float(job.salary_max) if job.salary_max is not None else None,
        )
        low, high = rules.yearly_eur(structured)
        if low is not None or high is not None:
            features.salary_min_eur, features.salary_max_eur = low, high
            features.salary_currency, features.salary_period = "EUR", "year"
            features.origin["salary"] = "source"
            return
    salary = rules.salary_in_text(job.description)
    if salary is None:
        return
    features.salary_currency, features.salary_period = salary.currency, salary.period
    features.salary_min_eur, features.salary_max_eur = rules.yearly_eur(salary)
    features.origin["salary"] = "rule"
