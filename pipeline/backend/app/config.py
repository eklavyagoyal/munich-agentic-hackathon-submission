"""Paths and environment. No third-party deps so every module can import it."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"
DB_PATH = DATA / "c2f.sqlite"
CASES_ZIPS = DATA / "cases" / "zips"          # encrypted archives (copied from organizers' folder)
CASES_EXTRACTED = DATA / "cases" / "extracted" # per-game decrypted files

LEADERBOARD_BASE = "https://c2f.public.quantco.cloud/leaderboard/api"
TEAM_BASE = "https://c2f.public.quantco.cloud"

OUR_TEAM = "Oasis"

# Where the organizers' encrypted zips already live on this machine (repo v1 checkout).
V1_CASES_DIR = Path(os.environ.get(
    "C2F_V1_CASES",
    "/Users/luis/Documents/agentic-hackathon-submission/public-cases-ehl/cases",
))


def _load_dotenv() -> None:
    """Tiny .env loader — KEY=VALUE lines, no quoting games."""
    env = ROOT / ".env"
    if not env.is_file():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())


_load_dotenv()

TEAM_API_KEY = os.environ.get("TEAM_API_KEY", "")
