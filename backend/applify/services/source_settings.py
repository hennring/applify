"""Sources on/off and their settings per user (F7d, table source_settings)."""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from applify.db.models import SourceSetting
from applify.sources.base import SourceConfig


@dataclass(frozen=True)
class SourceInfo:
    key: str
    label: str
    kind: str  # jobs / discovery
    description: str
    # Settings the user can enter; secrets are never sent back to the browser.
    fields: tuple[str, ...] = ()
    secrets: tuple[str, ...] = ()
    # Settings without which the source cannot run.
    required: tuple[str, ...] = ()


CATALOG: tuple[SourceInfo, ...] = (
    SourceInfo("ba", "Bundesagentur für Arbeit", "jobs", "Jobsuche-API der BA, mit Volltext."),
    SourceInfo(
        "arbeitnow",
        "Arbeitnow",
        "jobs",
        "Öffentliche Job-Board-API, Stellen aus ATS-Feeds, mit Volltext.",
    ),
    SourceInfo(
        "adzuna",
        "Adzuna",
        "jobs",
        "Aggregator-API, nur Kurzinfo. Kostenloser Key: developer.adzuna.com",
        fields=("app_id", "app_key"),
        secrets=("app_key",),
        required=("app_id", "app_key"),
    ),
    SourceInfo(
        "service_bund",
        "service.bund.de",
        "jobs",
        "Stellen im öffentlichen Dienst per RSS, nur Kurzinfo.",
    ),
    SourceInfo(
        "careers",
        "Karriereseiten",
        "jobs",
        "Firmen der Watchlist: ATS-Feeds (Personio, Greenhouse, Lever, Recruitee, "
        "SmartRecruiters, Workday) und JSON-LD.",
    ),
    SourceInfo(
        "github",
        "GitHub-Organisationen",
        "discovery",
        "Findet Firmen mit Sitz in den Profil-Orten. Ohne Token stark begrenzt.",
        fields=("token",),
        secrets=("token",),
    ),
    SourceInfo(
        "wikidata",
        "Wikidata",
        "discovery",
        "Findet Unternehmen mit Sitz im Umkreis der Profil-Orte. Braucht eine Kontaktadresse.",
    ),
)
BY_KEY = {info.key: info for info in CATALOG}
# Not a source: settings for all outgoing requests.
GENERAL = "general"


def load_settings(session: Session, user_id: int) -> dict[str, SourceConfig]:
    rows = {
        row.source: row
        for row in session.scalars(select(SourceSetting).where(SourceSetting.user_id == user_id))
    }
    return {
        key: SourceConfig(rows[key].enabled, dict(rows[key].config))
        if key in rows
        else SourceConfig()
        for key in [*BY_KEY, GENERAL]
    }


def save_setting(
    session: Session, user_id: int, key: str, *, enabled: bool | None = None, **config: Any
) -> SourceSetting:
    """Update one row; config values of None are removed, others replace the old ones."""
    row = session.scalar(
        select(SourceSetting).where(SourceSetting.user_id == user_id, SourceSetting.source == key)
    )
    if row is None:
        row = SourceSetting(user_id=user_id, source=key, enabled=True, config={})
        session.add(row)
    if enabled is not None:
        row.enabled = enabled
    merged = dict(row.config or {})
    for name, value in config.items():
        if value is None:
            merged.pop(name, None)
        else:
            merged[name] = value
    row.config = merged  # reassign: JSONB only notices new objects
    session.flush()
    return row


def missing(info: SourceInfo, config: SourceConfig) -> list[str]:
    return [name for name in info.required if not config.config.get(name)]
