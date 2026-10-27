from collections import Counter

from applify.services.skills import get_taxonomy

from applify_analytics.features.stacks import (
    assign,
    frequent_itemsets,
    select_stacks,
    stack_skills,
)


def test_frequent_itemsets_follow_the_apriori_property() -> None:
    jobs = [frozenset({"Java", "Spring", "PostgreSQL"})] * 3 + [frozenset({"Java", "React"})]
    frequent = frequent_itemsets(jobs, min_jobs=3)
    assert frequent[frozenset({"Java", "Spring", "PostgreSQL"})] == 3
    assert frequent[frozenset({"Java"})] == 4
    assert frozenset({"Java", "React"}) not in frequent


def test_stacks_drop_subsumed_sets_and_variants() -> None:
    java = frozenset({"Java", "Spring", "PostgreSQL", "Docker"})
    jobs = [java] * 10 + [frozenset({"Python", "Django", "PostgreSQL"})] * 8
    overall = Counter(skill for job in jobs for skill in job)
    stacks = select_stacks(frequent_itemsets(jobs, min_jobs=5), overall)
    # The 3-skill subsets of the Java stack always come with it and are not listed.
    assert [set(s.skills) for s in stacks] == [set(java), {"Python", "Django", "PostgreSQL"}]
    assert stacks[0].support == 10


def test_job_belongs_to_the_largest_stack_it_contains() -> None:
    java = frozenset({"Java", "Spring", "PostgreSQL", "Docker"})
    jobs = [java] * 10 + [frozenset({"Java", "Spring", "Kotlin"})] * 6
    overall = Counter(skill for job in jobs for skill in job)
    stacks = select_stacks(frequent_itemsets(jobs, min_jobs=5), overall)
    assert stacks[assign(java | {"Kafka"}, stacks) or 0].skills[0] == "Java"
    assert len(stacks[assign(java, stacks) or 0].skills) == 4
    assert assign({"Python"}, stacks) is None


def test_alternative_clouds_and_concepts_are_no_stack_skills() -> None:
    skills = ["Java", "AWS", "Azure", "Google Cloud", "CI/CD", "Scrum"]
    assert stack_skills(skills, get_taxonomy()) == {"Java"}
    assert stack_skills(["Java", "AWS"], get_taxonomy()) == {"Java", "AWS"}
