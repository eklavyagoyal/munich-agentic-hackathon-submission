"""The always-on loop: wake for every scheduled game and play it.

52 of the 100 games fall between 21:00 and 08:00 UTC (docs/leaderboard-api.md), so more
than half the tournament plays itself while nobody is at a keyboard. That makes this
loop most of the score, not insurance -- and "consistency" is a judged criterion.

Two hard rules, both learned from what a missed round costs (GAMEPLAN §3: a team that
submitted defaults scored -3247 while the winner made +6285):

  1. ONE BAD ROUND MUST NEVER KILL THE LOOP. Every failure is caught, logged and
     counted; the loop always advances to the next game. There is no exception type
     worth stopping 100 games for.
  2. THE CLOCK IS THE SERVER'S, NOT OURS. Timing comes from Leaderboard.server_now(),
     which corrects against the HTTP Date header. Our own clock measured 1.27s fast,
     which is 2% of a 60-second window given away before any network latency.

Time is injected (`sleep`, and the clock via the Leaderboard) so the whole loop is
testable in milliseconds instead of over 20 hours.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

from c2f.core.events import EventBus
from c2f.leaderboard import Game, Leaderboard
from c2f.runner import RoundConfig, Runner


@dataclass
class SchedulerConfig:
    cases_dir: Path = Path("cases")
    # Wake this far ahead of start_time so the process is warm and polling for the key
    # the instant it exists. Not earlier: fetching a key before release is off limits.
    lead_s: float = 3.0
    # Re-read the schedule this often; games may be added or rescheduled mid-tournament.
    refresh_s: float = 600.0
    # Longest single sleep. Bounded so a schedule change is picked up within it and so
    # a suspended laptop cannot silently sleep through the rest of the tournament.
    max_sleep_s: float = 60.0
    # Alert (never stop) after this many consecutive failures.
    alert_after: int = 3
    # Archive filename patterns tried against cases_dir, in order. ⚠️ GUESS until we
    # see the shared folder; `{id}` is the game id.
    # starter_script.py names them `case_{game_id:02d}.zip` under ./cases -- that is
    # the documented layout and is tried first. The rest are tolerated variants.
    archive_globs: tuple[str, ...] = (
        "case_{id:02d}.zip", "case_{id}.zip", "case{id:02d}.zip",
        "case{id}.zip", "case-{id}.zip", "{id}.zip", "*{id}*.zip",
    )


@dataclass
class SchedulerState:
    played: list[int] = field(default_factory=list)
    failed: list[int] = field(default_factory=list)
    skipped: list[int] = field(default_factory=list)
    consecutive_failures: int = 0


class Scheduler:
    def __init__(
        self,
        leaderboard: Leaderboard,
        runner: Runner,
        bus: EventBus,
        config: SchedulerConfig | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.lb = leaderboard
        self.runner = runner
        self.bus = bus
        self.cfg = config or SchedulerConfig()
        self._sleep = sleep
        self.state = SchedulerState()
        self._games: list[Game] = []
        self._games_at: datetime | None = None

    # -- schedule ---------------------------------------------------------

    def _schedule(self, now: datetime) -> list[Game]:
        """Cached game list, refreshed every `refresh_s`. A failed refresh keeps the
        stale list: playing from slightly old data beats not playing."""
        stale = self._games_at is None or (now - self._games_at).total_seconds() >= self.cfg.refresh_s
        if stale:
            try:
                games = self.lb.games()
                if games:
                    self._games, self._games_at = games, now
                    self.bus.emit("schedule.loaded", n=len(games),
                                  skew_s=round(self.lb.clock_skew_s, 3))
                else:
                    self.bus.emit("alert", level="warn", msg="schedule came back empty")
            except Exception as e:
                self.bus.emit("alert", level="warn",
                              msg=f"schedule refresh failed ({type(e).__name__}: {e}), using cache")
        return self._games

    def _due(self, games: list[Game], now: datetime) -> Game | None:
        """The next game we have not attempted whose start is still ahead of us."""
        seen = set(self.state.played) | set(self.state.failed) | set(self.state.skipped)
        for g in games:
            if g.id in seen or not g.scheduled:
                continue
            if g.start_time >= now - timedelta(seconds=self.cfg.lead_s):
                return g
        return None

    # -- archives ---------------------------------------------------------

    def archive_for(self, game: Game) -> Path | None:
        """Locate the encrypted archive for a game. ⚠️ Naming is a guess (ASKS.md)."""
        d = self.cfg.cases_dir
        if not d.is_dir():
            return None
        for pattern in self.cfg.archive_globs:
            pat = pattern.format(id=game.id)
            exact = d / pat
            if "*" not in pat and exact.is_file():
                return exact
            hits = sorted(p for p in d.glob(pat) if p.is_file())
            if hits:
                return hits[0]
        return None

    # -- the loop ---------------------------------------------------------

    def tick(self) -> bool:
        """Advance by one step. True if there may be more work, False when done.

        Sleeps until the next game is due, plays it, records the outcome. Never raises
        for a round failure -- the whole point is that the loop survives them.
        """
        now = self.lb.server_now()
        games = self._schedule(now)
        if not games:
            self.bus.emit("alert", level="warn", msg="no schedule available; waiting")
            self._sleep(self.cfg.max_sleep_s)
            return True

        game = self._due(games, now)
        if game is None:
            return False  # every game attempted

        wait = (game.start_time - now).total_seconds() - self.cfg.lead_s
        if wait > 0:
            # Capped so a schedule change is noticed and a suspended host recovers.
            self._sleep(min(wait, self.cfg.max_sleep_s))
            if wait > self.cfg.max_sleep_s:
                return True  # not yet; re-evaluate with a fresh clock

        archive = self.archive_for(game)
        if archive is None:
            self.state.skipped.append(game.id)
            self.bus.emit("alert", level="error",
                          msg=f"game {game.id}: no archive in {self.cfg.cases_dir} -- cannot play")
            return True

        cfg = RoundConfig(round_no=game.id, case_id=str(game.id), archive=archive)
        try:
            self.runner.run_round(cfg)
            self.state.played.append(game.id)
            self.state.consecutive_failures = 0
            self.bus.emit("round.played", game=game.id, played=len(self.state.played))
        except Exception as e:
            # Deliberately broad: nothing is worth abandoning the remaining games for.
            self.state.failed.append(game.id)
            self.state.consecutive_failures += 1
            self.bus.emit("alert", level="error",
                          msg=f"game {game.id} failed ({type(e).__name__}: {e})")
            if self.state.consecutive_failures >= self.cfg.alert_after:
                self.bus.emit("alert", level="error",
                              msg=f"{self.state.consecutive_failures} rounds failed in a row "
                                  f"-- something systemic is wrong, still going")
        return True

    def run(self, max_ticks: int | None = None) -> SchedulerState:
        """Play until the schedule is exhausted. `max_ticks` bounds it for tests."""
        ticks = 0
        while max_ticks is None or ticks < max_ticks:
            ticks += 1
            if not self.tick():
                break
        self.bus.emit("scheduler.done", played=len(self.state.played),
                      failed=len(self.state.failed), skipped=len(self.state.skipped))
        return self.state
