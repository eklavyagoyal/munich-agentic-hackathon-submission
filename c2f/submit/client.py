"""The API seam.

We have no credentials, no folder link and no API_HANDBOOK yet, so the live
client is a stub and everything is built against `MockApi`. When the handbook
lands, `LiveApi` is filled in and the swap is one line in the runner -- nothing
upstream of this file knows the difference.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from c2f.core.models import Submission


class ReadOnlyMachine(RuntimeError):
    """Raised instead of submitting when C2F_READONLY is set. Loud on purpose: a
    silent no-op would look exactly like a successful round in the event log."""


@dataclass
class SubmitResult:
    ok: bool
    status: int
    detail: str = ""
    # The rows the server says it stored. API_HANDBOOK documents the PUT response as
    # echoing them back, so verification comes free with the write -- no second
    # request, and no window in which we believe a submission landed that did not.
    echo: list[dict[str, Any]] | None = None


class ApiClient(Protocol):
    def fetch_key(self, case_id: str) -> str: ...
    def submit(self, submission: Submission) -> SubmitResult: ...
    def get_submission(self, case_id: str) -> list[dict[str, Any]] | None: ...


class MockApi:
    """Local stand-in. Also the single-writer coordination primitive we hope
    the real API gives us: `get_submission` answers "does a submission already
    exist?" without any shared state of our own (ARCHITECTURE.md §3)."""

    def __init__(self, keys: dict[str, str], store: Path | None = None) -> None:
        self._keys = keys
        self._store = store
        self.sent: list[Submission] = []

    def fetch_key(self, case_id: str) -> str:
        if case_id not in self._keys:
            raise KeyError(f"no key released for {case_id}")
        return self._keys[case_id]

    def submit(self, submission: Submission) -> SubmitResult:
        self.sent.append(submission)
        payload = submission.payload()
        if self._store is not None:
            self._store.parent.mkdir(parents=True, exist_ok=True)
            self._store.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        # Mirror the live API: echo back in the server's field naming.
        echo = [{"line_item_index": r["index"], "charge_price": r["charge_price"],
                 "acceptance_limit": r["acceptance_limit"]} for r in payload]
        return SubmitResult(ok=True, status=200, echo=echo)

    def get_submission(self, case_id: str) -> list[dict[str, Any]] | None:
        for s in reversed(self.sent):
            if s.case_id == case_id:
                return s.payload()
        return None


class LiveApi:
    """The tournament API, per API_HANDBOOK.md and starter_script.py.

    No longer guessed. Every one of the five things this file previously assumed was
    wrong, and each would have failed silently or wholesale:

      auth      X-API-Key, NOT `Authorization: Bearer`   -> 401 on every call
      method    PUT, NOT POST                            -> every submission lost
      body      a BARE ARRAY, not {case_id, items: [...]} -> 422
      item key  "index", not "idx"/"position"             -> prices on wrong items
      key field "decryption_key", not "key"               -> never decrypts
      paths     /api/games/{id}/..., not /api/cases/...   -> 404

    Game 0 is a permanent test game, always available, so the whole round trip can
    be proven before a scheduled game starts.
    """

    BASE = os.environ.get("C2F_BASE", "https://c2f.public.quantco.cloud").rstrip("/")
    PATH_LIST = "/api/games/list"
    PATH_KEY = "/api/games/{game_id}/key"
    PATH_SUBMIT = "/api/games/{game_id}/submissions"
    TIMEOUT = (2.0, 5.0)   # (connect, read): a hung request must never eat the round

    def __init__(self, team_key: str | None = None, dry_run: bool = False) -> None:
        self.team_key = team_key if team_key is not None else os.environ.get("TEAM_API_KEY", "")
        self.dry_run = dry_run

    def _headers(self) -> dict[str, str]:
        if not self.team_key:
            raise RuntimeError("TEAM_API_KEY not set -- put it in .env (never commit it)")
        return {"X-API-Key": self.team_key, "Content-Type": "application/json"}

    def fetch_key(self, case_id: str, poll_for: float = 20.0) -> str:
        """Poll for the decryption key: bounded, backing off. The key is not there
        early, so a single failed request is expected rather than an error."""
        import requests

        # Validate config BEFORE the loop. A missing key is not transient, and
        # swallowing it into the retry loop burns a third of the round before
        # telling anyone.
        headers = self._headers()
        url = self.BASE + self.PATH_KEY.format(game_id=case_id)
        deadline = time.monotonic() + poll_for
        delay, last = 0.25, ""
        while time.monotonic() < deadline:
            try:
                r = requests.get(url, headers=headers, timeout=self.TIMEOUT)
                if r.ok:
                    ctype = r.headers.get("content-type", "")
                    key = (r.json().get("decryption_key")
                           if ctype.startswith("application/json") else r.text.strip())
                    if key:
                        return key
                # 403 before start_time is EXPECTED while polling; 401/404 are not
                # and will never resolve, so fail fast instead of burning the round.
                if r.status_code in (401, 404):
                    raise RuntimeError(
                        f"key fetch for game {case_id}: HTTP {r.status_code} {r.text[:160]}"
                        + (" -- check TEAM_API_KEY" if r.status_code == 401 else "")
                    )
                last = f"HTTP {r.status_code} {r.text[:120]}"
            except RuntimeError:
                raise
            except Exception as e:  # noqa: BLE001
                last = f"{type(e).__name__}: {e}"
            time.sleep(delay)
            delay = min(delay * 1.3, 2.0)
        raise TimeoutError(f"no key for {case_id} after {poll_for}s (last: {last})")

    def submit(self, submission: Submission) -> SubmitResult:
        import requests

        # A dry run issues no request at all, so it is safe on a read-only machine
        # and must keep working there -- that is where you test. Checked first.
        if self.dry_run:
            return SubmitResult(ok=True, status=0, detail="dry run -- not posted")

        # Machine-wide kill switch, for every box that is NOT the primary runner.
        # Later submissions overwrite earlier ones, so a second writer does not add
        # redundancy -- it silently replaces the primary's better answer with its
        # own. `--dry-run` is a flag a tired caller forgets at 03:00; C2F_READONLY
        # is set once in that machine's .env and cannot be forgotten per-command.
        # Off by default: the primary sets nothing and behaves exactly as before.
        if os.environ.get("C2F_READONLY", "").strip() not in ("", "0", "false", "no"):
            raise ReadOnlyMachine(
                f"C2F_READONLY is set: refusing to PUT game {submission.case_id}. "
                "This machine is not the primary runner. Unset it in .env if it is.")
        headers = self._headers()
        body = submission.payload()
        url = self.BASE + self.PATH_SUBMIT.format(game_id=submission.case_id)
        last = ""
        for attempt in (1, 2, 3):
            try:
                r = requests.put(url, headers=headers, json=body, timeout=self.TIMEOUT)
                if r.ok:
                    try:
                        echo = r.json()
                    except ValueError:
                        echo = None
                    return SubmitResult(ok=True, status=r.status_code,
                                        echo=echo if isinstance(echo, list) else None)
                last = f"HTTP {r.status_code} {r.text[:200]}"
                if 400 <= r.status_code < 500:
                    return SubmitResult(ok=False, status=r.status_code, detail=last)
            except Exception as e:  # noqa: BLE001
                last = f"{type(e).__name__}: {e}"
            time.sleep(0.4 * attempt)
        return SubmitResult(ok=False, status=0, detail=last)

    def games(self) -> list[dict[str, Any]]:
        """The authoritative schedule: [{id, start_time}]. Authenticated, unlike the
        public leaderboard feed, and it includes the always-available test game 0."""
        import requests

        r = requests.get(self.BASE + self.PATH_LIST, headers=self._headers(),
                         timeout=self.TIMEOUT)
        r.raise_for_status()
        return r.json()

    def get_submission(self, case_id: str) -> list[dict[str, Any]] | None:
        """API_HANDBOOK documents no read-back GET, so verification uses the PUT
        response echo (SubmitResult.echo) instead. None, not an exception, so the
        runner records what it knows rather than pretending either way."""
        return None
