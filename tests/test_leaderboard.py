"""Schedule handling. The cadence is never assumed: the slides say 10 minutes, the
challenge page says 15, and the API says 757.576 -- so we read it."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from c2f.leaderboard import Game, Leaderboard

START = datetime(2026, 8, 22, 13, 0, tzinfo=timezone.utc)
GAP = 757.575758


def fake(items, headers=None, status=200):
    body = json.dumps({"items": items, "page": 1, "page_size": 1000,
                       "total": len(items), "total_pages": 1})
    return lambda url: (status, body, headers or {})


def schedule(n=100):
    return [{"id": i + 1,
             "start_time": (START + timedelta(seconds=GAP * i)).isoformat().replace("+00:00", "Z"),
             "status": "scheduled"} for i in range(n)]


def test_reads_the_full_schedule():
    lb = Leaderboard(fetch=fake(schedule()))
    games = lb.games()
    assert len(games) == 100
    assert games[0].start_time == START
    assert all(g.scheduled for g in games)


def test_cadence_is_measured_not_assumed():
    lb = Leaderboard(fetch=fake(schedule()))
    cadence = Leaderboard.cadence(lb.games())
    assert cadence == pytest.approx(757.576, abs=0.01)
    assert cadence not in (600.0, 900.0)      # neither the slides nor the listing


def test_next_game_is_the_first_one_still_ahead():
    lb = Leaderboard(fetch=fake(schedule()))
    games = lb.games()
    now = START + timedelta(seconds=GAP * 3 + 5)
    assert lb.next_game(now=now, games=games).id == 5


def test_no_next_game_after_the_last_one():
    lb = Leaderboard(fetch=fake(schedule(3)))
    games = lb.games()
    assert lb.next_game(now=START + timedelta(days=2), games=games) is None


def test_clock_skew_is_taken_from_the_server():
    """A 60-second window does not forgive a laptop three seconds fast."""
    future = datetime.now(timezone.utc) + timedelta(seconds=42)
    hdr = {"Date": future.strftime("%a, %d %b %Y %H:%M:%S GMT")}
    lb = Leaderboard(fetch=fake(schedule(2), headers=hdr))
    lb.games()
    assert lb.clock_skew_s == pytest.approx(42, abs=2)


def test_missing_date_header_leaves_skew_unknown():
    lb = Leaderboard(fetch=fake(schedule(2)))
    lb.games()
    assert lb.clock_skew_s is None


def test_performance_404_is_not_an_error():
    """The API 404s with 'No completed rounds for that team' before we have played."""
    lb = Leaderboard(fetch=lambda url: (404, '{"detail":"No completed rounds"}', {}))
    assert lb.performance("us") is None


def test_server_error_is_raised_not_swallowed():
    lb = Leaderboard(fetch=lambda url: (500, "boom", {}))
    with pytest.raises(RuntimeError, match="HTTP 500"):
        lb.games()


def test_transactions_requires_both_params_in_the_url():
    seen = {}

    def spy(url):
        seen["url"] = url
        return 200, '{"items":[]}', {}

    Leaderboard(fetch=spy).transactions(game_id=7, team="Ingenious Inigo")
    assert "game_id=7" in seen["url"] and "team=Ingenious+Inigo" in seen["url"]
