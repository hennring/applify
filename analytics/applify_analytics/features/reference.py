"""Reference tables for dbt from the YAML files in the repo (single source of truth).

skills.yaml and roles.yaml stay the only place to edit; seeds would duplicate them.
"""

from applify.db.models import Profile
from applify.services.skills import get_taxonomy
from sqlalchemy import Column, Integer, String, Table, delete, insert, select
from sqlalchemy.engine import Connection

from applify_analytics.features.regions import refresh_states
from applify_analytics.features.rules import get_role_rules
from applify_analytics.features.store import ensure_tables, metadata

# skill_taxonomy, role_families and profile_role_families; the states come from regions.
skill_taxonomy = Table(
    "skill_taxonomy",
    metadata,
    Column("skill", String(100), primary_key=True),
    Column("category", String(30), nullable=False),
)
role_families = Table(
    "role_families",
    metadata,
    Column("role_family", String(30), primary_key=True),
    Column("label", String(100), nullable=False),
    Column("sort_order", Integer, nullable=False),
)
# The user's desired roles mapped to families, for the profile gap (F23).
profile_role_families = Table(
    "profile_role_families",
    metadata,
    Column("user_id", Integer, primary_key=True),
    Column("role", String(200), primary_key=True),
    Column("role_family", String(30)),
)


def refresh_reference(conn: Connection) -> dict[str, int]:
    ensure_tables(conn)
    rules = get_role_rules()
    skills = [{"skill": s.name, "category": s.category} for s in get_taxonomy().skills]
    families = [
        {"role_family": f.key, "label": f.label, "sort_order": i}
        for i, f in enumerate(rules.families)
    ]
    roles = [
        {"user_id": user_id, "role": role, "role_family": rules.classify(role)}
        for user_id, profile_roles in conn.execute(select(Profile.user_id, Profile.roles))
        for role in dict.fromkeys(profile_roles)
    ]
    for table, rows in (
        (skill_taxonomy, skills),
        (role_families, families),
        (profile_role_families, roles),
    ):
        conn.execute(delete(table))
        if rows:
            conn.execute(insert(table), rows)
    return {
        "skills": len(skills),
        "role_families": len(families),
        "profile_roles": len(roles),
        "states": refresh_states(conn),
    }
