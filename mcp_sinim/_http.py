"""Private networking layer for the SINIM API.

Wraps :class:`httpx.Client` with the courtesy the SINIM server expects
(see ``CLAUDE.md``): two documented header profiles, a minimum interval
between requests, retries with exponential backoff, explicit timeouts, and
detection of the server's HTML "Error inesperado" page (surfaced as
:class:`SINIMError`).

Header profiles
---------------
* **browser** — the form page, the variable catalog and the municipios
  endpoint reject non-browser callers ("Error inesperado") unless they send
  a real browser ``User-Agent`` plus ``Referer`` / ``X-Requested-With``.
* **data** — the XML data endpoint additionally requires
  ``X-Request-Source: r``.

Both profiles use the documented browser ``User-Agent``: the SINIM
endpoints reject the neutral project UA, so it is not used here.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

#: Browser User-Agent the SINIM endpoints require (see ``CLAUDE.md``).
BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/18.3.1 Safari/605.1.15"
)
#: Base path of the SINIM municipal-data application.
BASE_URL = "https://datos.sinim.gov.cl/datos_municipales"
#: Referer expected by the AJAX endpoints.
REFERER = f"{BASE_URL}.php"
#: Marker string of the server's generic failure page.
_ERROR_MARKER = "Error inesperado"


class SINIMError(RuntimeError):
    """Raised when SINIM returns an error page or an unrecoverable response."""


def browser_headers() -> dict[str, str]:
    """Header profile for the form page, catalog and municipios endpoints."""
    return {
        "User-Agent": BROWSER_UA,
        "Referer": REFERER,
        "X-Requested-With": "XMLHttpRequest",
        "Accept-Encoding": "gzip, deflate, br",
    }


def data_headers() -> dict[str, str]:
    """Header profile for the XML data endpoint (adds ``X-Request-Source``)."""
    return {
        "User-Agent": BROWSER_UA,
        "Referer": REFERER,
        "X-Request-Source": "r",
        "Accept-Encoding": "gzip, deflate, br",
    }


class HttpClient:
    """Courteous :class:`httpx.Client` wrapper for the SINIM endpoints.

    Parameters
    ----------
    timeout:
        Per-request timeout in seconds.
    min_interval:
        Minimum wall-clock gap (seconds) enforced between successive
        requests. Defaults to ``0.5`` (project rate-limit policy).
    max_retries:
        Number of attempts for transport/timeout/5xx failures.
    backoff_factor:
        Base of the exponential backoff (``backoff_factor * 2**attempt``).
    """

    def __init__(
        self,
        timeout: float = 30,
        min_interval: float = 0.5,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
    ) -> None:
        self.timeout = timeout
        self.min_interval = min_interval
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self._client = httpx.Client(timeout=timeout, follow_redirects=True)
        self._last_request = 0.0

    def __enter__(self) -> HttpClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying transport."""
        self._client.close()

    def _throttle(self) -> None:
        """Sleep so successive requests honor :attr:`min_interval`."""
        if self.min_interval <= 0:
            return
        elapsed = time.monotonic() - self._last_request
        wait = self.min_interval - elapsed
        if wait > 0:
            time.sleep(wait)

    def _check(self, response: httpx.Response) -> httpx.Response:
        """Raise :class:`SINIMError` on error pages, else return response."""
        # The failure page is short HTML served with a 200 status.
        head = response.content[:4096].decode("latin-1", errors="ignore")
        if _ERROR_MARKER in head:
            raise SINIMError(
                "SINIM returned its 'Error inesperado' page. This usually "
                "means required headers (browser User-Agent / X-Requested-With "
                "/ X-Request-Source) are missing or the request parameters are "
                f"invalid. URL: {response.request.url}"
            )
        response.raise_for_status()
        return response

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        params: Any = None,
        data: Any = None,
    ) -> httpx.Response:
        """Perform a rate-limited request with retry/backoff and error checks.

        Retries transport errors, timeouts and 5xx responses up to
        :attr:`max_retries`; :class:`SINIMError` (error page) and 4xx are not
        retried. Raises the last error if every attempt fails.
        """
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            self._throttle()
            try:
                response = self._client.request(
                    method, url, headers=headers, params=params, data=data
                )
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_exc = exc
            else:
                self._last_request = time.monotonic()
                if response.status_code >= 500:
                    last_exc = httpx.HTTPStatusError(
                        f"server error {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                else:
                    return self._check(response)
            self._last_request = time.monotonic()
            if attempt < self.max_retries - 1:
                time.sleep(self.backoff_factor * (2**attempt))
        assert last_exc is not None
        raise last_exc

    def get(self, url: str, *, headers: dict[str, str], params: Any = None) -> httpx.Response:
        """Convenience wrapper for a GET request."""
        return self.request("GET", url, headers=headers, params=params)

    def post(self, url: str, *, headers: dict[str, str], data: Any = None) -> httpx.Response:
        """Convenience wrapper for a POST request."""
        return self.request("POST", url, headers=headers, data=data)
