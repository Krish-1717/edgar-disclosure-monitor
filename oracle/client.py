"""SEC fair-access HTTP client: global rate limit, retries with backoff."""
from __future__ import annotations

import email.utils
import logging
import random
import threading
import time
from typing import Callable

import httpx

from .config import DEFAULT_RPS, SEC_MAX_RPS, ConfigError, validate_user_agent
from . import __version__

log = logging.getLogger(__name__)

RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})


class SecHttpError(RuntimeError):
    def __init__(self, url: str, status: int | None, message: str):
        super().__init__(f"{message} ({status or 'no response'}) for {url}")
        self.url = url
        self.status = status


class RateLimiter:
    """Minimum-interval limiter shared by every request (SEC counts per client, all hosts)."""

    def __init__(
        self,
        max_rps: float = DEFAULT_RPS,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if not (0 < max_rps <= SEC_MAX_RPS):
            raise ConfigError(f"max_rps must be in (0, {SEC_MAX_RPS}]")
        self.interval = 1.0 / max_rps
        self._clock = clock
        self._sleep = sleep
        self._next = float("-inf")
        self._lock = threading.Lock()

    def acquire(self) -> None:
        with self._lock:
            now = self._clock()
            wait = self._next - now
            if wait > 0:
                self._sleep(wait)
                now = self._next
            self._next = now + self.interval


def _retry_after_seconds(value: str | None) -> float | None:
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        return float(value)
    try:
        dt = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, dt.timestamp() - time.time())


class SecClient:
    """Thin httpx wrapper that every ORACLE request goes through."""

    def __init__(
        self,
        user_agent: str | None,
        max_rps: float = DEFAULT_RPS,
        max_retries: int = 4,
        backoff_base: float = 1.0,
        backoff_cap: float = 60.0,
        timeout: float = 30.0,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        transport: httpx.BaseTransport | None = None,
    ):
        ua = validate_user_agent(user_agent)
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.backoff_cap = backoff_cap
        self._sleep = sleep
        self.limiter = RateLimiter(max_rps, clock=clock, sleep=sleep)
        self.request_count = 0
        self._client = httpx.Client(
            headers={
                "User-Agent": ua,
                "Accept-Encoding": "gzip, deflate",
                "X-Client": f"ORACLE/{__version__}",
            },
            timeout=timeout,
            follow_redirects=True,
            transport=transport,
        )

    # -- lifecycle -------------------------------------------------------------
    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "SecClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- requests --------------------------------------------------------------
    def _backoff(self, attempt: int) -> float:
        delay = min(self.backoff_cap, self.backoff_base * (2 ** attempt))
        return delay * (1.0 + 0.25 * random.random())   # jitter

    def get(self, url: str) -> httpx.Response:
        last_status: int | None = None
        for attempt in range(self.max_retries + 1):
            self.limiter.acquire()
            self.request_count += 1
            try:
                resp = self._client.get(url)
            except httpx.TransportError as exc:
                if attempt >= self.max_retries:
                    raise SecHttpError(url, None, f"transport error: {exc}") from exc
                delay = self._backoff(attempt)
                log.warning("transport error on %s (%s); retry in %.1fs", url, exc, delay)
                self._sleep(delay)
                continue

            last_status = resp.status_code
            if resp.status_code in RETRY_STATUSES:
                if attempt >= self.max_retries:
                    break
                retry_after = _retry_after_seconds(resp.headers.get("Retry-After"))
                delay = min(self.backoff_cap, retry_after) if retry_after is not None else self._backoff(attempt)
                log.warning("HTTP %s on %s; retry %d in %.1fs", resp.status_code, url, attempt + 1, delay)
                self._sleep(delay)
                continue
            if resp.status_code == 403:
                raise SecHttpError(url, 403, "forbidden - check the User-Agent / request rate")
            if resp.status_code >= 400:
                raise SecHttpError(url, resp.status_code, "HTTP error")
            return resp
        raise SecHttpError(url, last_status, f"gave up after {self.max_retries + 1} attempts")

    def get_json(self, url: str):
        return self.get(url).json()

    def get_bytes(self, url: str) -> bytes:
        return self.get(url).content
