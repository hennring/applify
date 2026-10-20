import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

SKILLS_FILE = Path(__file__).parents[2] / "resources" / "skills.yaml"

# Aliases that are also everyday words; they only count with their exact spelling.
AMBIGUOUS_ALIASES = frozenset(
    {"solid", "express", "spring", "swift", "remix", "elastic", "phoenix", "astro", "shell"}
)


@dataclass(frozen=True)
class Skill:
    name: str
    category: str
    synonyms: tuple[str, ...] = field(default=())


@dataclass(frozen=True)
class Mention:
    skill: Skill
    snippet: str


def match_key(text: str) -> str:
    """Comparison key: case-insensitive, ignores spaces, dots, hyphens and underscores.

    '#', '+' and '/' are kept so that C, C#, C++ and CI/CD stay distinct.
    """
    return re.sub(r"[\s.\-_]", "", text.casefold())


@lru_cache(maxsize=4096)
def alias_pattern(alias: str) -> re.Pattern[str]:
    """Regex that finds an alias in free text.

    Separators are optional ("Vue.js" finds "VueJS" and "Vue JS"), and the alias must not
    be part of a longer word ("Java" does not match "JavaScript", "React" not "Reactive").
    Short aliases ("Go", "C", "Java") and everyday words are case-sensitive; the shortest
    ones also must not be glued to a hyphen, so "Go-Live" is not Go.
    """
    chunks = [re.escape(c) for c in re.split(r"[\s.\-_]+", alias) if c]
    body = r"[\s.\-_]?".join(chunks)
    key = match_key(alias)
    edge = r"\w#+\-" if len(key) <= 2 else r"\w#+"
    flags = 0 if len(key) <= 4 or alias.casefold() in AMBIGUOUS_ALIASES else re.IGNORECASE
    return re.compile(rf"(?<![{edge}]){body}(?![{edge}])", flags)


def mentions(alias: str, text: str) -> bool:
    return alias_pattern(alias).search(text) is not None


class SkillTaxonomy:
    def __init__(self, skills: list[Skill]) -> None:
        self.skills = skills
        self._by_key: dict[str, Skill] = {}
        for skill in skills:
            for alias in (skill.name, *skill.synonyms):
                key = match_key(alias)
                if key in self._by_key and self._by_key[key] is not skill:
                    raise ValueError(f"ambiguous skill alias {alias!r}")
                self._by_key[key] = skill

    @classmethod
    def from_yaml(cls, path: Path) -> "SkillTaxonomy":
        entries = yaml.safe_load(path.read_text(encoding="utf-8"))
        return cls(
            [
                Skill(e["name"], e["category"], tuple(str(s) for s in e.get("synonyms", [])))
                for e in entries
            ]
        )

    def lookup(self, name: str) -> Skill | None:
        return self._by_key.get(match_key(name))

    def find_mentions(self, text: str) -> list[Mention]:
        """All known skills mentioned in a text, in order of first appearance."""
        found: list[tuple[int, Mention]] = []
        for skill in self.skills:
            hits = [
                m
                for alias in (skill.name, *skill.synonyms)
                if (m := alias_pattern(alias).search(text))
            ]
            if hits:
                first = min(hits, key=lambda m: m.start())
                snippet = text[max(0, first.start() - 40) : first.end() + 40]
                found.append((first.start(), Mention(skill, re.sub(r"\s+", " ", snippet).strip())))
        return [mention for _, mention in sorted(found, key=lambda f: f[0])]


@lru_cache
def get_taxonomy() -> SkillTaxonomy:
    return SkillTaxonomy.from_yaml(SKILLS_FILE)
