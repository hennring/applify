import pytest

from applify.services.skills import SkillTaxonomy, get_taxonomy, match_key, mentions


@pytest.fixture(scope="module")
def taxonomy() -> SkillTaxonomy:
    return get_taxonomy()


def test_taxonomy_loads_without_ambiguous_aliases(taxonomy: SkillTaxonomy) -> None:
    assert len(taxonomy.skills) >= 150


@pytest.mark.parametrize(
    ("alias", "canonical"),
    [
        ("vue.js", "Vue"),
        ("VueJS", "Vue"),
        ("JS", "JavaScript"),
        ("node", "Node.js"),
        ("Postgres", "PostgreSQL"),
        ("C#", "C#"),
        ("c++", "C++"),
        ("ci/cd", "CI/CD"),
        ("Barrierefreiheit", "Accessibility"),
    ],
)
def test_lookup_by_synonym(taxonomy: SkillTaxonomy, alias: str, canonical: str) -> None:
    skill = taxonomy.lookup(alias)
    assert skill is not None
    assert skill.name == canonical


def test_lookup_unknown(taxonomy: SkillTaxonomy) -> None:
    assert taxonomy.lookup("Basket weaving") is None


def test_match_key_keeps_distinguishing_symbols() -> None:
    assert len({match_key("C"), match_key("C#"), match_key("C++")}) == 3


@pytest.mark.parametrize(
    ("alias", "text", "expected"),
    [
        ("Vue.js", "Erfahrung mit VueJS und Pinia", True),
        ("Vue.js", "Vue JS", True),
        ("React", "React-Entwickler gesucht", True),
        ("React", "reactive programming", False),
        ("Java", "JavaScript und TypeScript", False),
        ("Go", "Go-Live im März", False),
        ("Go", "Backend in Go und Rust", True),
        ("C", "Level C1", False),
        ("Express", "express your ideas", False),
        ("Express", "Node.js mit Express", True),
        ("PostgreSQL", "postgresql, redis", True),
    ],
)
def test_mentions(alias: str, text: str, expected: bool) -> None:
    assert mentions(alias, text) is expected


def test_find_mentions_in_order_with_snippet(taxonomy: SkillTaxonomy) -> None:
    found = taxonomy.find_mentions("Wir nutzen Docker. Frontend in Vue 3 mit TypeScript.")
    assert [m.skill.name for m in found] == ["Docker", "Vue", "TypeScript"]
    assert "Vue 3" in found[1].snippet
