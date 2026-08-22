"""Public leaderboard API client. Read-only, unauthenticated."""
from __future__ import annotations

from .config import LEADERBOARD_BASE
from .http import get_json


def games() -> list[dict]:
    d = get_json(f"{LEADERBOARD_BASE}/games", params={"page_size": 1000})
    return d["items"]


def matrix() -> list[dict]:
    d = get_json(f"{LEADERBOARD_BASE}/matrix", params={"page": 1, "game_limit": 1000})
    return d["items"]


def performance(team: str) -> dict:
    return get_json(f"{LEADERBOARD_BASE}/performance", params={"team": team})


def transactions(game_id: int, team: str) -> list[dict]:
    """All pages for one (game, team). Rows: issuer, reviewer, line_item_index, accepted, amount."""
    rows: list[dict] = []
    page = 1
    while True:
        d = get_json(f"{LEADERBOARD_BASE}/transactions",
                     params={"game_id": game_id, "team": team, "page": page, "page_size": 500})
        rows.extend(d["items"])
        if page >= d.get("total_pages", 1):
            return rows
        page += 1
