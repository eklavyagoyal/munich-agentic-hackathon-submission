"""The public leaderboard feed: schedule, standings, and per-transaction results.

Two jobs:

1. **When does the next round start.** The schedule is published exactly, for all 100
   games, before the tournament begins -- so we never hardcode a cadence and never
   trust the local clock. See docs/leaderboard-api.md.
2. **What happened afterwards.** `transactions` is the only source of the
   interval-censored bounds on `t` that the calibration loop needs, and the only read
   we get on how the opponent field behaves.

This is the same JSON feed the public leaderboard page reads. Poll it at browser-tab
rates; GAME_DESCRIPTION forbids hammering the infrastructure.
"""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable

BASE = "https://c2f.public.quantco.cloud"
PREFIX = "/leaderboard/api"
TIMEOUT = 5.0


@dataclass(frozen=True)
class Game:
    id: int
    start_time: datetime
    status: str

    @property
    def scheduled(self) -> bool:
        return self.status == "scheduled"


def _default_fetch(url: str) -> tuple[int, str, dict[str, str]]:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.status, r.read().decode("utf-8"), dict(r.headers)


class Leaderboard:
    def __init__(self, base: str = BASE,
                 fetch: Callable[[str], tuple[int, str, dict[str, str]]] | None = None) -> None:
        self.base = base.rstrip("/")
        self._fetch = fetch or _default_fetch
        self.clock_skew_s: float | None = None

    def _get(self, path: str, **params: Any) -> Any:
        from urllib.parse import urlencode

        url = f"{self.base}{PREFIX}{path}"
        if params:
            url += "?" + urlencode({k: v for k, v in params.items() if v is not None})
        status, body, headers = self._fetch(url)
        if status == 404:
            return None
        if status >= 400:
            raise RuntimeError(f"{path} -> HTTP {status}: {body[:200]}")
        self._note_skew(headers)
        return json.loads(body)

    def _note_skew(self, headers: dict[str, str]) -> None:
        """Trust the server's clock, not ours. A 60-second window does not forgive
        a laptop that is three seconds fast."""
        raw = headers.get("Date") or headers.get("date")
        if not raw:
            return
        try:
            server = parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            return
        if server.tzinfo is None:
            server = server.replace(tzinfo=timezone.utc)
        self.clock_skew_s = (server - datetime.now(timezone.utc)).total_seconds()

    # -- schedule --------------------------------------------------------
    def games(self, completed_only: bool = False, page_size: int = 1000) -> list[Game]:
        data = self._get("/games", completed_only=str(completed_only).lower(),
                         page_size=page_size) or {}
        out = []
        for it in data.get("items", []):
            ts = it["start_time"].replace("Z", "+00:00")
            out.append(Game(id=it["id"], start_time=datetime.fromisoformat(ts),
                            status=it["status"]))
        return sorted(out, key=lambda g: g.start_time)

    def next_game(self, now: datetime | None = None,
                  games: list[Game] | None = None) -> Game | None:
        """The next game that has not started yet, by SERVER time."""
        now = now or self.server_now()
        for g in games if games is not None else self.games():
            if g.start_time > now:
                return g
        return None

    def server_now(self) -> datetime:
        now = datetime.now(timezone.utc)
        if self.clock_skew_s is None:
            return now
        return now.fromtimestamp(now.timestamp() + self.clock_skew_s, tz=timezone.utc)

    @staticmethod
    def cadence(games: list[Game]) -> float | None:
        """Observed seconds between games. Reported, never assumed -- the slides say
        10 minutes, the challenge page says 15, and the API says 757.576."""
        if len(games) < 2:
            return None
        gaps = [(b.start_time - a.start_time).total_seconds()
                for a, b in zip(games, games[1:])]
        return sum(gaps) / len(gaps)

    # -- results ---------------------------------------------------------
    def transactions(self, game_id: int, team: str) -> list[dict[str, Any]]:
        """Per-transaction outcomes. The calibration loop's only source of bounds on
        `t`: a rejection reveals which side of the threshold a charge fell on, while
        an acceptance reveals nothing (ARCHITECTURE.md §8)."""
        data = self._get("/transactions", game_id=game_id, team=team) or {}
        return data.get("items", [])

    def performance(self, team: str) -> dict[str, Any] | None:
        """None until the team has completed a round -- the API 404s until then."""
        return self._get("/performance", team=team)

    def matchup(self, team: str) -> list[dict[str, Any]]:
        return (self._get("/matchup", team=team) or {}).get("items", [])

    def standings(self, game_limit: int = 20) -> list[dict[str, Any]]:
        return (self._get("/matrix", page=1, game_limit=game_limit) or {}).get("items", [])
