"""Authenticated team API: decryption keys. This module never submits."""
from __future__ import annotations

from .config import TEAM_API_KEY, TEAM_BASE
from .http import get_json


def fetch_key(game_id: int) -> str:
    """Decryption key for a started game. 403 before start_time."""
    if not TEAM_API_KEY:
        raise RuntimeError("TEAM_API_KEY missing — put it in .env")
    d = get_json(f"{TEAM_BASE}/api/games/{game_id}/key",
                 headers={"X-API-Key": TEAM_API_KEY})
    return d["decryption_key"]
