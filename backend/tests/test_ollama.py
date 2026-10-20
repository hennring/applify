import json
from typing import Any

import httpx
import pytest
from pydantic import BaseModel

from applify.llm import LLMError
from applify.llm.ollama import OllamaProvider


class Answer(BaseModel):
    city: str
    population: int


def provider(*contents: str, status: int = 200) -> tuple[OllamaProvider, list[dict[str, Any]]]:
    """Provider whose Ollama server answers with the given message contents in order."""
    requests: list[dict[str, Any]] = []
    answers = iter(contents)

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(status, json={"message": {"content": next(answers, "")}})

    client = httpx.Client(base_url="http://ollama", transport=httpx.MockTransport(handle))
    return OllamaProvider("http://ollama", "qwen3:14b", num_ctx=8192, client=client), requests


def test_generate_structured_sends_schema_and_options() -> None:
    llm, requests = provider('{"city": "Leipzig", "population": 620000}')
    answer = llm.generate_structured("Frage", Answer, system="System")
    assert answer == Answer(city="Leipzig", population=620000)
    body = requests[0]
    assert body["format"] == Answer.model_json_schema()
    assert body["think"] is False
    assert body["options"] == {"num_ctx": 8192, "temperature": 0}
    assert [m["role"] for m in body["messages"]] == ["system", "user"]


def test_generate_structured_retries_once_with_error() -> None:
    llm, requests = provider('{"city": "Leipzig"}', '{"city": "Leipzig", "population": 1}')
    assert llm.generate_structured("Frage", Answer).population == 1
    retry_messages = requests[1]["messages"]
    assert retry_messages[-2]["role"] == "assistant"
    assert "population" in retry_messages[-1]["content"]


def test_generate_structured_fails_after_second_invalid_answer() -> None:
    llm, _ = provider("kein json", "immer noch nicht")
    with pytest.raises(LLMError, match="after retry"):
        llm.generate_structured("Frage", Answer)


def test_http_errors_become_llm_errors() -> None:
    llm, _ = provider("", status=500)
    with pytest.raises(LLMError, match="request failed"):
        llm.generate("Hallo")


def test_generate_returns_text() -> None:
    llm, requests = provider("Hallo zurück")
    assert llm.generate("Hallo") == "Hallo zurück"
    assert "format" not in requests[0]
