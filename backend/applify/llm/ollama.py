from typing import Any

import httpx
from pydantic import ValidationError

from applify.llm.base import LLMError, T

Message = dict[str, str]


class OllamaProvider:
    """LLMProvider backed by a local Ollama server (D2, D3).

    Structured output uses Ollama's `format` parameter with the JSON schema of the
    Pydantic model (D5). If the answer still fails validation, the error is sent back
    once so the model can correct itself.
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        num_ctx: int = 8192,
        timeout: float = 300,
        client: httpx.Client | None = None,
    ) -> None:
        self.model = model
        self.num_ctx = num_ctx
        self._client = client or httpx.Client(base_url=base_url, timeout=timeout)

    def generate(self, prompt: str, *, system: str | None = None) -> str:
        return self._chat(self._messages(prompt, system), temperature=0.7)

    def generate_structured(self, prompt: str, schema: type[T], *, system: str | None = None) -> T:
        messages = self._messages(prompt, system)
        json_schema = schema.model_json_schema()
        content = self._chat(messages, format=json_schema, temperature=0)
        try:
            return schema.model_validate_json(content)
        except ValidationError as first_error:
            messages += [
                {"role": "assistant", "content": content},
                {
                    "role": "user",
                    "content": "Your answer did not match the schema. Fix these errors and "
                    f"answer again with the complete JSON:\n{first_error}",
                },
            ]
            content = self._chat(messages, format=json_schema, temperature=0)
            try:
                return schema.model_validate_json(content)
            except ValidationError as exc:
                raise LLMError(f"invalid structured output after retry: {exc}") from exc

    @staticmethod
    def _messages(prompt: str, system: str | None) -> list[Message]:
        messages = [{"role": "system", "content": system}] if system else []
        return [*messages, {"role": "user", "content": prompt}]

    def _chat(self, messages: list[Message], *, temperature: float, format: Any = None) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            # qwen3 would otherwise emit a long reasoning block before every answer.
            "think": False,
            "options": {"num_ctx": self.num_ctx, "temperature": temperature},
        }
        if format is not None:
            payload["format"] = format
        try:
            response = self._client.post("/api/chat", json=payload)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMError(f"Ollama request failed: {exc}") from exc
        content: str = response.json()["message"]["content"]
        return content
