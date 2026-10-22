"""HTTP client with the fetching etiquette from N6."""

import time
from typing import Any
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from applify.sources.base import SourceError

USER_AGENT = "Applify/0.1 (personal job search assistant)"
# Pages larger than this are not read (careers pages, sitemaps).
MAX_PAGE_BYTES = 5_000_000
# Unreachable company websites should not hold up a run for long.
CONNECT_TIMEOUT = 8.0


def user_agent(contact: str) -> str:
    return f"{USER_AGENT[:-1]}; +{contact})" if contact else USER_AGENT


def host_of(url: str) -> str:
    return urlsplit(url).netloc


class PoliteClient:
    """At most one request per `interval` seconds and host; errors become SourceError."""

    def __init__(
        self,
        *,
        contact: str = "",
        interval: float = 1.0,
        timeout: float = 20.0,
        ipv4_only: bool = True,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.interval = interval
        self.contact = contact
        self._last: dict[str, float] = {}
        self._robots: dict[str, RobotFileParser | None] = {}
        if transport is None and ipv4_only:
            # httpx tries the addresses one after another without "happy eyeballs": without
            # an IPv6 route every connection to a dual-stack host first waits for the
            # connect timeout. Binding to an IPv4 address skips the IPv6 attempt.
            transport = httpx.HTTPTransport(local_address="0.0.0.0")
        self._client = httpx.Client(
            headers={"User-Agent": user_agent(contact)},
            timeout=httpx.Timeout(timeout, connect=CONNECT_TIMEOUT),
            follow_redirects=True,
            transport=transport,
        )

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        host = host_of(url)
        wait = self._last.get(host, 0.0) + self.interval - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        try:
            response = self._client.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            raise SourceError(f"{host}: {type(exc).__name__}") from exc
        except ValueError as exc:  # malformed URL from a page or a user
            raise SourceError(f"{url[:100]}: ungültige URL") from exc
        finally:
            self._last[host] = time.monotonic()
        return response

    def get_ok(self, url: str, **kwargs: Any) -> httpx.Response:
        response = self.request("GET", url, **kwargs)
        if response.status_code != httpx.codes.OK:
            raise SourceError(f"{host_of(url)}: HTTP {response.status_code}")
        return response

    def get_json(self, url: str, **kwargs: Any) -> Any:
        response = self.get_ok(url, **kwargs)
        try:
            return response.json()
        except ValueError as exc:
            raise SourceError(f"{host_of(url)}: keine gültige JSON-Antwort") from exc

    def get_conditional(self, url: str, etag: str | None, **kwargs: Any) -> httpx.Response | None:
        """GET with If-None-Match (N6); None if the resource is unchanged."""
        headers = dict(kwargs.pop("headers", None) or {})
        if etag:
            headers["If-None-Match"] = etag
        response = self.request("GET", url, headers=headers, **kwargs)
        if response.status_code == httpx.codes.NOT_MODIFIED:
            return None
        if response.status_code != httpx.codes.OK:
            raise SourceError(f"{host_of(url)}: HTTP {response.status_code}")
        return response

    def allowed(self, url: str) -> bool:
        """robots.txt check for pages of company websites (N6); APIs are meant for clients."""
        parts = urlsplit(url)
        key = f"{parts.scheme}://{parts.netloc}"
        if key not in self._robots:
            parser: RobotFileParser | None = None
            try:
                response = self.request("GET", f"{key}/robots.txt")
            except SourceError:
                response = None
            if response is not None and response.status_code == httpx.codes.OK:
                parser = RobotFileParser()
                parser.parse(response.text.splitlines())
            elif response is not None and response.status_code in (401, 403):
                parser = RobotFileParser()
                parser.parse(["User-agent: *", "Disallow: /"])
            self._robots[key] = parser  # None: no robots.txt, everything allowed
        parser = self._robots[key]
        return parser is None or parser.can_fetch(USER_AGENT.split("/")[0], url)

    def get_page(self, url: str) -> httpx.Response:
        """A public web page, honouring robots.txt."""
        if not self.allowed(url):
            raise SourceError(f"{host_of(url)}: laut robots.txt nicht erlaubt")
        response = self.get_ok(url)
        if len(response.content) > MAX_PAGE_BYTES:
            raise SourceError(f"{host_of(url)}: Seite zu groß")
        return response

    def close(self) -> None:
        self._client.close()
