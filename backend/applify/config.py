from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APPLIFY_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://applify:applify@localhost:5432/applify"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:14b"
    data_dir: Path = Path("../data/files")
    # Built SvelteKit SPA; only served if the directory exists.
    static_dir: Path = Path("../frontend/build")


@lru_cache
def get_settings() -> Settings:
    return Settings()
