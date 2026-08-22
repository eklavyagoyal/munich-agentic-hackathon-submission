"""Append-only event stream -- the backbone (PIPELINE.md §2).

One stream serves four consumers: the live UI, offline replay, the calibration
dataset, and the strategy write-up. So we instrument once.

The hot path must NEVER be slowed by a consumer. Subscribers get a bounded
queue and are dropped from it on overflow; the JSONL sink is the only
guaranteed-durable path.
"""
from __future__ import annotations

import json
import queue
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

SUBSCRIBER_QUEUE_SIZE = 512


@dataclass
class Event:
    ts: float
    round: int
    case: str
    seq: int
    type: str
    payload: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(
            {"ts": self.ts, "round": self.round, "case": self.case,
             "seq": self.seq, "type": self.type, "payload": self.payload},
            separators=(",", ":"), default=str,
        )


class EventBus:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path
        self._fh = None
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._fh = path.open("a", encoding="utf-8")
        self._seq = 0
        self._lock = threading.Lock()
        self._subs: list[queue.Queue[Event]] = []
        self.dropped = 0
        self.round = 0
        self.case = ""

    def bind(self, round: int, case: str) -> None:
        self.round, self.case = round, case

    def emit(self, type: str, **payload: Any) -> Event:
        with self._lock:
            self._seq += 1
            ev = Event(time.time(), self.round, self.case, self._seq, type, payload)
            if self._fh is not None:
                self._fh.write(ev.to_json() + "\n")
                self._fh.flush()
        for q in list(self._subs):
            try:
                q.put_nowait(ev)
            except queue.Full:
                # Never block the hot path on a slow consumer.
                self.dropped += 1
        return ev

    def subscribe(self) -> queue.Queue[Event]:
        q: queue.Queue[Event] = queue.Queue(maxsize=SUBSCRIBER_QUEUE_SIZE)
        self._subs.append(q)
        return q

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None


def read_events(path: Path) -> list[Event]:
    """Replay support: rebuild the stream from disk."""
    out: list[Event] = []
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        out.append(Event(d["ts"], d["round"], d["case"], d["seq"], d["type"], d["payload"]))
    return out
