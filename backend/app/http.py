"""One shared HTTP session: bounded retries, polite pacing, hard timeouts.

Fair play: the public leaderboard endpoints are the page's own data feed; we poll
at browser-tab rate, never hammer. A small concurrency cap + per-request pause
keeps the full harvest around a minute without bursts.
"""
from __future__ import annotations

import time

import requests

TIMEOUT = (3.05, 15)
ATTEMPTS = 3
PAUSE = 0.08  # seconds between requests per worker

_session = requests.Session()
_session.headers["User-Agent"] = "oasis-analysis/2.0"


def get_json(url: str, params: dict | None = None, headers: dict | None = None):
    """GET with retries. Raises for non-2xx after retrying 5xx/connection errors.
    404 raises immediately (it is an answer, not a failure)."""
    last = None
    for attempt in range(ATTEMPTS):
        try:
            r = _session.get(url, params=params, headers=headers, timeout=TIMEOUT)
            if r.status_code == 404:
                r.raise_for_status()
            if r.status_code >= 500:
                raise requests.HTTPError(f"{r.status_code} server error", response=r)
            r.raise_for_status()
            time.sleep(PAUSE)
            return r.json()
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code in (403, 404, 422):
                raise
            last = e
        except (requests.ConnectionError, requests.Timeout) as e:
            last = e
        time.sleep(0.5 * (attempt + 1))
    raise last  # type: ignore[misc]
