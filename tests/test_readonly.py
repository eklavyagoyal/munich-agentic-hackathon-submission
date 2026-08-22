"""The kill switch for every machine that is not the primary runner.

Two writers is not redundancy. `PUT` is last-write-wins, so a backup posting its
crude fallback at T+55s replaces the primary's good answer from T+50s. These
tests are the guarantee that a machine marked read-only cannot do that.
"""
from __future__ import annotations

import pytest

from c2f.core.models import Decision, Submission
from c2f.submit.client import LiveApi, ReadOnlyMachine


def _sub() -> Submission:
    return Submission(case_id="7", tier=1,
                      decisions=(Decision(idx=1, a=10.0, b=12.0, covered=True, belief=None),))


def test_readonly_blocks_submit(monkeypatch):
    monkeypatch.setenv("TEAM_API_KEY", "k")
    monkeypatch.setenv("C2F_READONLY", "1")
    with pytest.raises(ReadOnlyMachine):
        LiveApi().submit(_sub())


def test_readonly_beats_dry_run_being_forgotten(monkeypatch):
    """The point of the switch: it wins even when the caller forgot every flag."""
    monkeypatch.setenv("TEAM_API_KEY", "k")
    monkeypatch.setenv("C2F_READONLY", "true")
    with pytest.raises(ReadOnlyMachine):
        LiveApi(dry_run=False).submit(_sub())


@pytest.mark.parametrize("value", ["", "0", "false", "no"])
def test_unset_or_falsey_leaves_the_primary_alone(monkeypatch, value):
    """The primary sets nothing and must behave exactly as before. Checked via
    dry_run so the test never touches the network."""
    monkeypatch.setenv("TEAM_API_KEY", "k")
    monkeypatch.setenv("C2F_READONLY", value)
    assert LiveApi(dry_run=True).submit(_sub()).ok


def test_absent_variable_leaves_the_primary_alone(monkeypatch):
    monkeypatch.setenv("TEAM_API_KEY", "k")
    monkeypatch.delenv("C2F_READONLY", raising=False)
    assert LiveApi(dry_run=True).submit(_sub()).ok


def test_backtest_never_constructs_a_live_client():
    """The structural half of the guarantee: the backtest harness has no code path
    that can PUT, regardless of environment variables."""
    import inspect
    import tools.backtest as bt

    src = inspect.getsource(bt)
    assert "MockApi" in src
    # LiveApi appears only inside KeyVault.fetch, and only for the GET.
    assert ".submit(" not in src
