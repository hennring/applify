from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APPLIFY_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://applify:applify@127.0.0.1:5432/applify"
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:14b"
    # Ollama defaults to 4096 tokens, too small for a CV plus prompt and schema.
    ollama_num_ctx: int = 8192
    data_dir: Path = Path("../data/files")
    max_upload_mb: int = 15
    # Contact for the User-Agent of outgoing requests (N6), e.g. a mail address or URL.
    http_contact: str = ""
    # Seconds between two requests to the same host (N6).
    http_interval: float = 1.0
    # Connect via IPv4 only; set to false on networks with working IPv6.
    http_ipv4_only: bool = True
    # Built SvelteKit SPA; only served if the directory exists.
    static_dir: Path = Path("../frontend/build")


@lru_cache
def get_settings() -> Settings:
    return Settings()
