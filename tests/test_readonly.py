"""The kill switch for every machine that is not the primary runner.

Two writers is not redundancy. `PUT` is last-write-wins, so a backup posting its
crude fallback at T+55s replaces the primary's good answer from T+50s. These
tests are the guarantee that a machine marked read-only cannot do that.
"""
from __future__ import annotations

import json

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


def test_readonly_blocks_when_dry_run_was_forgotten(monkeypatch):
    """The point of the switch: it wins when the caller forgot --dry-run.

    A real dry run is allowed through -- it issues no request, and a read-only
    machine is exactly where you want to be able to dry-run."""
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


def test_backtest_disables_model_network_unless_explicit(monkeypatch):
    from c2f.estimate import llm
    import tools.backtest as bt

    monkeypatch.setenv("C2F_BACKEND", "openai")
    llm.reset()
    bt.configure_model_network(False)
    assert llm.backend() == "none"
    llm.reset()


def test_key_vault_rejects_corrupt_cache_instead_of_hiding_it(tmp_path):
    import tools.backtest as bt

    path = tmp_path / "keys.json"
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(RuntimeError, match="unreadable"):
        bt.KeyVault(path)


def test_key_vault_writes_atomically_with_private_permissions(tmp_path):
    import tools.backtest as bt

    path = tmp_path / "keys.json"
    vault = bt.KeyVault(path)
    vault.store({1: "synthetic-key"})
    assert json.loads(path.read_text(encoding="utf-8")) == {"1": "synthetic-key"}
    assert path.stat().st_mode & 0o777 == 0o600
