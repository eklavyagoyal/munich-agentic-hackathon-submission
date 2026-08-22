"""The API seam.

We have no credentials, no folder link and no API_HANDBOOK yet, so the live
client is a stub and everything is built against `MockApi`. When the handbook
lands, `LiveApi` is filled in and the swap is one line in the runner -- nothing
upstream of this file knows the difference.
"""
from __future__ import annotations

import json
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
    """Filled in once API_HANDBOOK.md is available. See PIPELINE.md §9 for the
    five things we need to look up first -- especially how line items are keyed
    in the payload."""

    def __init__(self, base_url: str, team_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.team_key = team_key

    def fetch_key(self, case_id: str) -> str:
        raise NotImplementedError("blocked on API_HANDBOOK.md")

    def submit(self, submission: Submission) -> SubmitResult:
        raise NotImplementedError("blocked on API_HANDBOOK.md")

    def get_submission(self, case_id: str) -> dict[str, Any] | None:
        raise NotImplementedError("blocked on API_HANDBOOK.md")
