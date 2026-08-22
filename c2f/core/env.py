"""Load `.env` into the environment. Imported by `c2f/__init__.py`, so it applies to
every entrypoint without each one remembering to call it.

Exists because submit/client.py tells the operator to "put it in .env" and nothing was
reading that file -- the key would have been silently ignored at 03:00, with no round
submitted and no error pointing at the cause.

Real environment variables always win, so an inline `KEY=... python ...` overrides the
file, and CI never picks up a developer's local secrets.
"""
from __future__ import annotations

import os
from pathlib import Path


def load(path: Path | None = None) -> list[str]:
    """Set any KEY=VALUE from `.env` that is not already in os.environ.

    Returns the names loaded -- never the values, which are secrets and must not reach
    a log. A missing or unreadable file is not an error: the vars may be set directly.
    """
    env = path or Path.cwd() / ".env"
    if not env.is_file():
        return []
    try:
        text = env.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    loaded: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        line = line.removeprefix("export ").lstrip()
        key, sep, value = line.partition("=")
        key = key.strip()
        if not sep or not key or any(c in key for c in " \t"):
            continue
        value = value.strip()
        # Strip one matching pair of surrounding quotes, as a shell would.
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key not in os.environ:
            os.environ[key] = value
            loaded.append(key)
    return loaded
