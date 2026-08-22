"""The tournament API and archive decryption.

⚠️  EVERY CONSTANT AND PAYLOAD SHAPE IN THIS FILE IS A GUESS. We have not seen
    API_HANDBOOK.md yet. This is deliberately the only file that needs to change when
    it lands — nothing above it knows the wire format. Fix BASE, the three paths and
    `_payload`, then re-run `python run.py --self-test`.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import requests

from .llm import log

BASE = os.environ.get("C2F_BASE", "https://c2f.public.quantco.cloud")
PATH_KEY = "/api/cases/{case_id}/key"  # ← guess
PATH_SUBMIT = "/api/cases/{case_id}/submission"  # ← guess
PATH_SCHEDULE = "/api/schedule"  # ← guess

TIMEOUT = (2.0, 5.0)  # (connect, read) — a hung request must never eat the round


def _headers() -> dict:
    key = os.environ.get("TEAM_API_KEY")
    if not key:
        raise RuntimeError("TEAM_API_KEY not set — put it in .env (never commit it)")
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def fetch_key(case_id: str, *, poll_for: float = 20.0) -> str:
    """Poll for the decryption key. Bounded, backing off — the key is not there early.

    ponytail: fixed 250ms floor with mild growth. Not a full backoff-with-jitter policy
    because this is one client polling one endpoint it is *expected* to poll; upgrade if
    the organisers publish a rate limit.
    """
    url = BASE + PATH_KEY.format(case_id=case_id)
    deadline = time.monotonic() + poll_for
    delay, attempt = 0.25, 0
    last = ""
    while time.monotonic() < deadline:
        attempt += 1
        try:
            r = requests.get(url, headers=_headers(), timeout=TIMEOUT)
            if r.ok:
                key = r.json().get("key") or r.text.strip()
                if key:
                    log.warning("key acquired for %s after %d attempts", case_id, attempt)
                    return key
            last = f"HTTP {r.status_code} {r.text[:120]}"
        except requests.RequestException as e:
            last = f"{type(e).__name__}: {e}"
        time.sleep(delay)
        delay = min(delay * 1.3, 2.0)
    raise TimeoutError(f"no key for {case_id} after {poll_for}s (last: {last})")


def decrypt(zip_path: Path, key: str, out_dir: Path) -> Path:
    """7z with a password. Needs `brew install p7zip` (or apt p7zip-full) on the runner."""
    out_dir.mkdir(parents=True, exist_ok=True)
    exe = next((e for e in ("7z", "7zz", "7za") if _which(e)), None)
    if not exe:
        raise RuntimeError("no 7z on PATH — run: brew install p7zip")
    r = subprocess.run(
        [exe, "x", "-y", f"-p{key}", f"-o{out_dir}", str(zip_path)],
        capture_output=True,
        timeout=30,
    )
    if r.returncode != 0:
        raise RuntimeError(f"7z failed ({r.returncode}): {r.stderr.decode()[:300]}")
    return out_dir


def _which(name: str) -> bool:
    from shutil import which

    return which(name) is not None


def _payload(case_id: str, rows: list[dict]) -> dict:
    """⚠️ GUESS. `rows` are {position, charge, acceptance_limit} — gross totals."""
    return {
        "case_id": case_id,
        "items": [
            {
                "position": r["position"],
                "charge_price": round(float(r["a"]), 2),
                "acceptance_limit": round(float(r["b"]), 2),
            }
            for r in rows
        ],
    }


def submit(case_id: str, rows: list[dict], *, dry_run: bool = False, tag: str = "") -> bool:
    """Idempotent by design — later submissions overwrite earlier ones, so retry freely."""
    body = _payload(case_id, rows)
    Path("logs").mkdir(exist_ok=True)
    Path(f"logs/{case_id}{('-' + tag) if tag else ''}.json").write_text(json.dumps(body, indent=2))

    if dry_run:
        log.warning("DRY RUN — not posting %s (%d rows)", tag or case_id, len(rows))
        return True

    url = BASE + PATH_SUBMIT.format(case_id=case_id)
    for attempt in (1, 2, 3):
        try:
            r = requests.post(url, headers=_headers(), json=body, timeout=TIMEOUT)
            if r.ok:
                log.warning("submitted %s %s (%d rows)", case_id, tag, len(rows))
                return True
            log.error("submit %s rejected: HTTP %s %s", tag, r.status_code, r.text[:200])
            if 400 <= r.status_code < 500:
                return False  # our payload is wrong; retrying cannot fix it
        except requests.RequestException as e:
            log.error("submit %s attempt %d failed: %s", tag, attempt, e)
        time.sleep(0.4 * attempt)
    return False
