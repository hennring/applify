"""HTTP client with the fetching etiquette from N6."""

import time
from typing import Any
from urllib.parse import urlsplit

import httpx

from applify.sources.base import SourceError

USER_AGENT = "Applify/0.1 (personal job search assistant)"


def user_agent(contact: str) -> str:
    return f"{USER_AGENT[:-1]}; +{contact})" if contact else USER_AGENT


class PoliteClient:
    """At most one request per `interval` seconds and host; errors become SourceError."""

    def __init__(
        self,
        *,
        contact: str = "",
        interval: float = 1.0,
        timeout: float = 20.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.interval = interval
        self._last: dict[str, float] = {}
        self._client = httpx.Client(
            headers={"User-Agent": user_agent(contact)},
            timeout=timeout,
            follow_redirects=True,
            transport=transport,
        )

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        host = urlsplit(url).netloc
        wait = self._last.get(host, 0.0) + self.interval - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        try:
            response = self._client.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            raise SourceError(f"{host}: {type(exc).__name__}") from exc
        finally:
            self._last[host] = time.monotonic()
        return response

    def get_json(self, url: str, **kwargs: Any) -> Any:
        response = self.request("GET", url, **kwargs)
        if response.status_code != httpx.codes.OK:
            raise SourceError(f"{urlsplit(url).netloc}: HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError as exc:
            raise SourceError(f"{urlsplit(url).netloc}: keine gültige JSON-Antwort") from exc

    def close(self) -> None:
        self._client.close()
