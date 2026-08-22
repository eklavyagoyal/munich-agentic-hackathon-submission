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


@dataclass
class SubmitResult:
    ok: bool
    status: int
    detail: str = ""


class ApiClient(Protocol):
    def fetch_key(self, case_id: str) -> str: ...
    def submit(self, submission: Submission) -> SubmitResult: ...
    def get_submission(self, case_id: str) -> dict[str, Any] | None: ...


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
        if self._store is not None:
            self._store.parent.mkdir(parents=True, exist_ok=True)
            self._store.write_text(json.dumps(submission.payload(), indent=2), encoding="utf-8")
        return SubmitResult(ok=True, status=200)

    def get_submission(self, case_id: str) -> dict[str, Any] | None:
        for s in reversed(self.sent):
            if s.case_id == case_id:
                return s.payload()
        return None


class LiveApi:
    """The tournament API. Recovered from the standalone `c2f/api.py` client and
    put behind `ApiClient`, so the runner never knows which one it holds.

    WARNING: every constant and payload shape below is a GUESS -- API_HANDBOOK.md
    has not been published. This is deliberately the ONLY file that changes when
    it lands. PIPELINE.md lists what to look up first, especially how line items
    are keyed: a wrong key produces a submission that looks healthy and is
    scored as garbage.
    """

    BASE = os.environ.get("C2F_BASE", "https://c2f.public.quantco.cloud")
    PATH_KEY = "/api/cases/{case_id}/key"            # <- guess
    PATH_SUBMIT = "/api/cases/{case_id}/submission"  # <- guess
    TIMEOUT = (2.0, 5.0)   # (connect, read): a hung request must never eat the round

    def __init__(self, team_key: str | None = None, dry_run: bool = False) -> None:
        self.team_key = team_key if team_key is not None else os.environ.get("TEAM_API_KEY", "")
        self.dry_run = dry_run

    def _headers(self) -> dict[str, str]:
        if not self.team_key:
            raise RuntimeError("TEAM_API_KEY not set -- put it in .env (never commit it)")
        return {"Authorization": f"Bearer {self.team_key}", "Content-Type": "application/json"}

    def fetch_key(self, case_id: str, poll_for: float = 20.0) -> str:
        """Poll for the decryption key: bounded, backing off. The key is not there
        early, so a single failed request is expected rather than an error."""
        import requests

        # Validate config BEFORE the loop. A missing key is not transient, and
        # swallowing it into the retry loop burns a third of the round before
        # telling anyone.
        headers = self._headers()
        url = self.BASE + self.PATH_KEY.format(case_id=case_id)
        deadline = time.monotonic() + poll_for
        delay, last = 0.25, ""
        while time.monotonic() < deadline:
            try:
                r = requests.get(url, headers=headers, timeout=self.TIMEOUT)
                if r.ok:
                    ctype = r.headers.get("content-type", "")
                    key = r.json().get("key") if ctype.startswith("application/json") else r.text.strip()
                    if key:
                        return key
                last = f"HTTP {r.status_code} {r.text[:120]}"
            except Exception as e:  # noqa: BLE001
                last = f"{type(e).__name__}: {e}"
            time.sleep(delay)
            delay = min(delay * 1.3, 2.0)
        raise TimeoutError(f"no key for {case_id} after {poll_for}s (last: {last})")

    def submit(self, submission: Submission) -> SubmitResult:
        import requests

        if self.dry_run:
            return SubmitResult(ok=True, status=0, detail="dry run -- not posted")
        headers = self._headers()
        body = submission.payload()
        url = self.BASE + self.PATH_SUBMIT.format(case_id=submission.case_id)
        last = ""
        for attempt in (1, 2, 3):
            try:
                r = requests.post(url, headers=headers, json=body, timeout=self.TIMEOUT)
                if r.ok:
                    return SubmitResult(ok=True, status=r.status_code)
                last = f"HTTP {r.status_code} {r.text[:200]}"
                if 400 <= r.status_code < 500:
                    return SubmitResult(ok=False, status=r.status_code, detail=last)
            except Exception as e:  # noqa: BLE001
                last = f"{type(e).__name__}: {e}"
            time.sleep(0.4 * attempt)
        return SubmitResult(ok=False, status=0, detail=last)

    def get_submission(self, case_id: str) -> dict[str, Any] | None:
        """Read-back verification and the single-writer coordination primitive.
        Unknown whether the API offers it -- if not, the runner records
        `verified: None` rather than pretending."""
        raise NotImplementedError("read-back endpoint unknown until API_HANDBOOK.md")
