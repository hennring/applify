from collections.abc import Callable

from applify.config import get_settings
from applify.sources.adzuna import AdzunaSource
from applify.sources.arbeitnow import ArbeitnowSource
from applify.sources.arbeitsagentur import ArbeitsagenturSource
from applify.sources.base import FeedSource, JobSource, RunSources, SourceConfig, SourcesFactory
from applify.sources.http import PoliteClient
from applify.sources.service_bund import ServiceBundSource


def contact_of(settings: dict[str, SourceConfig]) -> str:
    """Contact for the User-Agent (N6): from the settings page, else from the environment."""
    general = settings.get("general")
    return (general.config.get("contact") if general else None) or get_settings().http_contact


def make_client(settings: dict[str, SourceConfig]) -> PoliteClient:
    return PoliteClient(contact=contact_of(settings), interval=get_settings().http_interval)


def build_sources(settings: dict[str, SourceConfig]) -> RunSources:
    """The enabled sources of one run (F7d)."""

    def on(key: str) -> bool:
        return settings.get(key, SourceConfig()).enabled

    client = make_client(settings)
    sources: list[JobSource] = []
    feeds: list[FeedSource] = []
    if on("ba"):
        sources.append(ArbeitsagenturSource(client))
    adzuna = settings.get("adzuna", SourceConfig()).config
    if on("adzuna") and adzuna.get("app_id") and adzuna.get("app_key"):
        sources.append(AdzunaSource(client, adzuna["app_id"], adzuna["app_key"]))
    if on("service_bund"):
        sources.append(ServiceBundSource(client))
    if on("arbeitnow"):
        feeds.append(ArbeitnowSource(client))
    return RunSources(sources, feeds, client)


def get_sources_factory() -> SourcesFactory:
    return build_sources


ClientFactory = Callable[[dict[str, SourceConfig]], PoliteClient]


def get_client_factory() -> ClientFactory:
    """HTTP client for requests made by the API itself (company detection)."""
    return make_client
