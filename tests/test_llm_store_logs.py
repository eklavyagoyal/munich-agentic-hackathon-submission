"""Request retention is opt-in, and OFF must be byte-identical to what shipped.

The Logs dashboard read empty for 27 rounds because `store` defaults off at the API.
Turning it on is a one-line change; the thing worth testing is the switch, because it
is the kill switch for a setting that asks a third party to KEEP our prompts.
"""
from __future__ import annotations

import pytest

from c2f.estimate import llm


@pytest.mark.parametrize("value,expected", [
    (None, True),        # unset: on, which is the deliberate default
    ("1", True),
    ("true", True),
    ("0", False),
    ("false", False),
    ("off", False),
    ("no", False),
    ("", False),         # explicitly blanked counts as off, not as unset
    ("  0  ", False),    # whitespace must not defeat the kill switch
    ("FALSE", False),    # nor case
])
def test_store_logs_flag(monkeypatch, value, expected):
    monkeypatch.delenv("C2F_STORE_LOGS", raising=False)
    if value is not None:
        monkeypatch.setenv("C2F_STORE_LOGS", value)
    assert llm.store_logs() is expected
