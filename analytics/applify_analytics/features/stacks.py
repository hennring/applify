"""Typical tech stacks (§5.9, D26): frequent skill sets in the postings.

Each IT job with full text is a transaction of its skills; the Apriori algorithm finds the
skill sets of 3 to 4 skills that at least MIN_JOBS jobs ask for together. A set is dropped
if a larger one almost always comes with it, and so are near-duplicates of better ones, so
a few distinct stacks remain. Each job then belongs to the largest selected stack it fully
contains.
"""

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from itertools import combinations

from applify.services.skills import SkillTaxonomy, get_taxonomy
from sqlalchemy import ARRAY, Column, Integer, String, Table, delete, insert, select
from sqlalchemy.engine import Connection

from applify_analytics.features.store import ensure_tables, job_features, metadata

MIN_JOBS = 8
MIN_SIZE, MAX_SIZE = 3, 4
MAX_STACKS = 20
# Stacks sharing more than this (Jaccard) with a better one are dropped as variants.
MAX_SIMILARITY = 0.6
# A set is subsumed by a larger one that has at least this share of its jobs.
SUBSUMED = 0.8
# Concepts rather than parts of a stack.
GENERIC = frozenset({"CI/CD", "REST", "Microservices"})
# Generic skills say little about a stack ("Git", "Scrum", "Figma").
STACK_CATEGORIES = frozenset(
    {
        "language", "frontend", "backend", "database", "devops", "cloud", "testing", "data",
        "ai", "mobile", "cms", "erp", "security",
    }
)  # fmt: skip

Itemset = frozenset[str]

skill_stacks = Table(
    "skill_stacks",
    metadata,
    Column("stack_id", Integer, primary_key=True),
    Column("skills", ARRAY(String), nullable=False),
    Column("support", Integer, nullable=False),
)
job_stacks = Table(
    "job_stacks",
    metadata,
    Column("job_id", Integer, primary_key=True),
    Column("stack_id", Integer, nullable=False),
)


@dataclass(frozen=True)
class Stack:
    skills: tuple[str, ...]  # most frequent skill first
    support: int


def frequent_itemsets(
    transactions: list[Itemset], min_jobs: int = MIN_JOBS, max_size: int = MAX_SIZE
) -> dict[Itemset, int]:
    """All skill sets up to max_size asked for by at least min_jobs transactions (Apriori)."""
    counts = Counter(skill for t in transactions for skill in t)
    level = {frozenset([s]): n for s, n in counts.items() if n >= min_jobs}
    frequent = dict(level)
    for size in range(2, max_size + 1):
        candidates = _candidates(set(level), size)
        if not candidates:
            break
        level = {}
        for candidate in candidates:
            support = sum(candidate <= t for t in transactions)
            if support >= min_jobs:
                level[candidate] = support
        frequent.update(level)
    return frequent


def _candidates(previous: set[Itemset], size: int) -> set[Itemset]:
    """Sets of the next size whose every subset is frequent (Apriori property)."""
    joined = {a | b for a, b in combinations(previous, 2) if len(a | b) == size}
    return {
        c for c in joined if all(frozenset(sub) in previous for sub in combinations(c, size - 1))
    }


def select_stacks(
    frequent: dict[Itemset, int], overall: Counter[str], limit: int = MAX_STACKS
) -> list[Stack]:
    """Frequent sets of at least MIN_SIZE skills not subsumed by a larger one, most jobs
    first, without near-duplicates."""
    sized = {s: n for s, n in frequent.items() if len(s) >= MIN_SIZE}
    kept = [s for s in sized if not any(s < o and sized[o] >= SUBSUMED * sized[s] for o in sized)]
    # More jobs first; among equal ones, the larger (more specific) stack.
    kept.sort(key=lambda s: (-sized[s], -len(s), sorted(s)))
    chosen: list[Itemset] = []
    for stack in kept:
        if all(len(stack & c) / len(stack | c) <= MAX_SIMILARITY for c in chosen):
            chosen.append(stack)
        if len(chosen) == limit:
            break
    return [
        Stack(tuple(sorted(s, key=lambda skill: (-overall[skill], skill))), sized[s])
        for s in chosen
    ]


def assign(job_skills: Iterable[str], stacks: list[Stack]) -> int | None:
    """Index of the largest stack the job fully contains, the more common one on a tie."""
    skills = set(job_skills)
    fitting = [i for i, s in enumerate(stacks) if set(s.skills) <= skills]
    return max(fitting, key=lambda i: (len(stacks[i].skills), stacks[i].support), default=None)


def stack_skills(skills: Iterable[str], taxonomy: SkillTaxonomy) -> Itemset:
    """The skills of a job that make up a stack. Several cloud providers in one posting are
    usually alternatives ("AWS, Azure oder GCP"), so they are left out then."""
    known = {
        s: skill.category
        for s in skills
        if (skill := taxonomy.lookup(s)) and skill.category in STACK_CATEGORIES and s not in GENERIC
    }
    clouds = [s for s, category in known.items() if category == "cloud"]
    return frozenset(s for s in known if len(clouds) < 2 or s not in clouds)


def refresh_stacks(conn: Connection) -> tuple[int, int]:
    """Find the stacks in the IT jobs with full text; returns (stacks, jobs assigned)."""
    from applify.db.models import Job

    ensure_tables(conn)
    taxonomy = get_taxonomy()
    rows = conn.execute(
        select(job_features.c.job_id, job_features.c.skills)
        .join(Job.__table__, Job.__table__.c.id == job_features.c.job_id)
        .where(
            Job.__table__.c.has_full_text,
            job_features.c.role_family.is_not(None),
            job_features.c.role_family != "other",
        )
    ).all()
    transactions = {row.job_id: stack_skills(row.skills, taxonomy) for row in rows}
    overall = Counter(skill for t in transactions.values() for skill in t)
    stacks = select_stacks(frequent_itemsets(list(transactions.values())), overall)
    assigned = [
        {"job_id": job_id, "stack_id": index + 1}
        for job_id, skills in transactions.items()
        if (index := assign(skills, stacks)) is not None
    ]
    conn.execute(delete(job_stacks))
    conn.execute(delete(skill_stacks))
    if stacks:
        conn.execute(
            insert(skill_stacks),
            [
                {"stack_id": i + 1, "skills": list(s.skills), "support": s.support}
                for i, s in enumerate(stacks)
            ],
        )
    if assigned:
        conn.execute(insert(job_stacks), assigned)
    return len(stacks), len(assigned)
