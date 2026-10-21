from applify.config import get_settings
from applify.sources.arbeitsagentur import ArbeitsagenturSource
from applify.sources.base import JobSource, SourcesFactory
from applify.sources.http import PoliteClient


def build_sources() -> list[JobSource]:
    """The sources of one run; more follow in M4, with on/off settings (F7d)."""
    settings = get_settings()
    client = PoliteClient(contact=settings.http_contact, interval=settings.http_interval)
    return [ArbeitsagenturSource(client)]


def get_sources_factory() -> SourcesFactory:
    return build_sources
