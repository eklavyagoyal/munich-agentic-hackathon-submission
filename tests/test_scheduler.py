"""The loop must survive everything, because 52 of 100 games run while we are asleep.

Time is injected, so a 20-hour tournament is exercised in milliseconds.
"""
from datetime import datetime, timedelta, timezone

import pytest

from c2f.core.events import EventBus, read_events
from c2f.leaderboard import Game
from c2f.scheduler import Scheduler, SchedulerConfig

T0 = datetime(2026, 8, 22, 13, 0, tzinfo=timezone.utc)


def games(n: int, every_s: float = 757.576) -> list[Game]:
    return [Game(id=i + 1, start_time=T0 + timedelta(seconds=every_s * i), status="scheduled")
            for i in range(n)]


class FakeLeaderboard:
    """Schedule source with a controllable clock."""

    clock_skew_s = 0.0

    def __init__(self, game_list, now=T0, fail_games=False):
        self._games = game_list
        self._now = now
        self.fail_games = fail_games
        self.games_calls = 0

    def games(self):
        self.games_calls += 1
        if self.fail_games:
            raise RuntimeError("leaderboard down")
        return self._games

    def server_now(self):
        return self._now

    def advance(self, seconds):
        self._now = self._now + timedelta(seconds=seconds)


class FakeRunner:
    """Records rounds; can be told to blow up."""

    def __init__(self, explode_on=()):
        self.rounds = []
        self.explode_on = set(explode_on)

    def run_round(self, cfg):
        self.rounds.append(cfg.case_id)
        if int(cfg.case_id) in self.explode_on:
            raise RuntimeError(f"round {cfg.case_id} exploded")
        return []


@pytest.fixture
def cases(tmp_path):
    for i in range(1, 6):
        (tmp_path / f"case{i}.zip").write_bytes(b"x")
    return tmp_path


def build(game_list, cases_dir, explode_on=(), fail_games=False, **kw):
    lb = FakeLeaderboard(game_list, fail_games=fail_games)
    runner = FakeRunner(explode_on)
    # Same idiom as test_e2e: persist to a file and read it back, which exercises the
    # real event path rather than an in-memory shortcut.
    bus = EventBus(cases_dir / "events.jsonl")
    cfg = SchedulerConfig(cases_dir=cases_dir, max_sleep_s=1e9, **kw)

    def sleep(seconds):
        lb.advance(seconds)          # sleeping moves the clock forward

    return Scheduler(lb, runner, bus, cfg, sleep=sleep), lb, runner


def alerts(sched) -> list[str]:
    sched.bus.close()
    return [e.payload.get("msg", "") for e in read_events(sched.bus._path) if e.type == "alert"]


def event_types(sched) -> list[str]:
    sched.bus.close()
    return [e.type for e in read_events(sched.bus._path)]


# -- the core promise -------------------------------------------------------

def test_plays_every_scheduled_game(cases):
    s, _, runner = build(games(5), cases)
    state = s.run(max_ticks=50)
    assert runner.rounds == ["1", "2", "3", "4", "5"]
    assert state.played == [1, 2, 3, 4, 5] and not state.failed


def test_a_failing_round_does_not_stop_the_loop(cases):
    """The single most important property in this file."""
    s, _, runner = build(games(5), cases, explode_on={2, 3})
    state = s.run(max_ticks=50)
    assert runner.rounds == ["1", "2", "3", "4", "5"]     # all still attempted
    assert state.played == [1, 4, 5]
    assert state.failed == [2, 3]


def test_every_round_failing_still_attempts_all_of_them(cases):
    s, _, runner = build(games(5), cases, explode_on={1, 2, 3, 4, 5})
    state = s.run(max_ticks=50)
    assert len(runner.rounds) == 5 and state.failed == [1, 2, 3, 4, 5]


def test_consecutive_failures_raise_a_loud_alert(cases):
    s, _, _ = build(games(4), cases, explode_on={1, 2, 3}, alert_after=3)
    s.run(max_ticks=50)
    assert any("in a row" in m for m in alerts(s))


def test_a_success_resets_the_failure_streak(cases):
    s, _, _ = build(games(4), cases, explode_on={1, 2})
    s.run(max_ticks=50)
    assert s.state.consecutive_failures == 0


# -- degraded inputs --------------------------------------------------------

def test_a_missing_archive_is_skipped_loudly_not_silently(cases):
    """Playing 4 of 5 games is survivable; not knowing why is not."""
    (cases / "case3.zip").unlink()
    s, _, runner = build(games(5), cases)
    state = s.run(max_ticks=50)
    assert runner.rounds == ["1", "2", "4", "5"]
    assert state.skipped == [3]
    assert any("no archive" in m for m in alerts(s))


def test_a_dead_leaderboard_keeps_playing_from_the_cached_schedule(cases):
    s, lb, runner = build(games(3), cases, refresh_s=0.0)   # refresh on every tick
    s.tick()                                                # first tick caches it
    lb.fail_games = True
    s.run(max_ticks=20)
    assert runner.rounds == ["1", "2", "3"]
    assert any("using cache" in m for m in alerts(s))


def test_no_schedule_at_all_waits_instead_of_crashing(cases):
    s, _, runner = build([], cases)
    s.tick()
    assert runner.rounds == []
    assert any("no schedule" in m for m in alerts(s))


def test_already_started_games_are_not_replayed(cases):
    """Restarting mid-tournament must resume, not replay from game 1."""
    late = T0 + timedelta(seconds=757.576 * 3)
    s, lb, runner = build(games(5), cases)
    lb._now = late
    s.run(max_ticks=50)
    assert "1" not in runner.rounds and "5" in runner.rounds


def test_completed_games_are_ignored(cases):
    gs = games(3)
    gs[0] = Game(id=1, start_time=gs[0].start_time, status="completed")
    s, _, runner = build(gs, cases)
    s.run(max_ticks=50)
    assert runner.rounds == ["2", "3"]


# -- timing -----------------------------------------------------------------

def test_long_waits_are_chunked_so_a_schedule_change_is_noticed(cases):
    """A single 20-hour sleep would miss any reschedule and never survive a suspend."""
    s, lb, _ = build(games(2), cases)
    s.cfg.max_sleep_s = 30.0
    slept = []
    s._sleep = lambda x: (slept.append(x), lb.advance(x))
    s.run(max_ticks=10)
    assert slept and max(slept) <= 30.0


def test_it_wakes_before_the_start_not_after(cases):
    s, lb, runner = build(games(1), cases, lead_s=3.0)
    s.cfg.max_sleep_s = 1e9
    s.tick()
    # It ran, and the clock at run time was at or before start_time.
    assert runner.rounds == ["1"]
    assert lb.server_now() <= T0


def test_archive_naming_variants_are_all_found(tmp_path):
    for name in ("case-2.zip", "case_3.zip", "4.zip", "weird-prefix-5-suffix.zip"):
        (tmp_path / name).write_bytes(b"x")
    (tmp_path / "case1.zip").write_bytes(b"x")
    s, _, _ = build(games(5), tmp_path)
    found = [s.archive_for(g) for g in games(5)]
    assert all(f is not None for f in found), found


def test_run_returns_a_summary(cases):
    (cases / "case4.zip").unlink()
    s, _, _ = build(games(5), cases, explode_on={2})
    state = s.run(max_ticks=50)
    assert (state.played, state.failed, state.skipped) == ([1, 3, 5], [2], [4])
    assert "scheduler.done" in event_types(s)
