from functools import lru_cache
from pathlib import Path

from applify.config import get_settings
from applify.llm.base import LLMError, LLMProvider
from applify.llm.ollama import OllamaProvider

__all__ = ["LLMError", "LLMProvider", "get_llm", "load_prompt"]

PROMPTS_DIR = Path(__file__).parent / "prompts"


@lru_cache
def get_llm() -> LLMProvider:
    settings = get_settings()
    return OllamaProvider(
        settings.ollama_url, settings.ollama_model, num_ctx=settings.ollama_num_ctx
    )


def load_prompt(name: str) -> str:
    """Load a versioned prompt template from llm/prompts/, e.g. 'cv_extraction_v1'."""
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
