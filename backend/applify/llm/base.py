from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """The provider failed or did not return a valid result."""


class LLMProvider(Protocol):
    """Provider-agnostic LLM interface (D4)."""

    def generate(self, prompt: str, *, system: str | None = None) -> str: ...

    def generate_structured(
        self, prompt: str, schema: type[T], *, system: str | None = None
    ) -> T: ...
