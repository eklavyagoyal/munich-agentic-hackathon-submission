"""Authenticated team API: decryption keys. This module never submits."""
from __future__ import annotations

import time

import requests

from .config import TEAM_API_KEY, TEAM_BASE


def fetch_key(game_id: int, poll_for: float = 30.0) -> str:
    """Decryption key for a game. The key returns 403 until start_time, and we
    arrive right at the boundary — so poll, bounded, with tight timeouts."""
    if not TEAM_API_KEY:
        raise RuntimeError("TEAM_API_KEY missing — put it in .env")
    url = f"{TEAM_BASE}/api/games/{game_id}/key"
    headers = {"X-API-Key": TEAM_API_KEY}
    deadline = time.monotonic() + poll_for
    delay = 0.3
    last = ""
    while time.monotonic() < deadline:
        try:
            r = requests.get(url, headers=headers, timeout=(2.0, 4.0))
            if r.status_code == 200:
                return r.json()["decryption_key"]
            last = f"{r.status_code}"
            if r.status_code not in (403, 404, 425, 429, 500, 502, 503):
                r.raise_for_status()
        except (requests.ConnectionError, requests.Timeout) as e:
            last = type(e).__name__
        time.sleep(delay)
        delay = min(delay * 1.5, 2.0)
    raise TimeoutError(f"no key for game {game_id} after {poll_for:.0f}s (last: {last})")
