"""Harvester labels and safety boundaries, using synthetic transactions only."""
from __future__ import annotations

import inspect
import stat
import zipfile

import pytest

from tools import harvest


def row(issuer, reviewer, accepted, amount, index=1):
    return {
        "issuer": issuer,
        "reviewer": reviewer,
        "line_item_index": index,
        "accepted": accepted,
        "amount": amount,
    }


def test_rejected_paid_is_lower_bound_and_rejected_unpaid_is_upper_bound():
    rows = [
        row("fair", "r1", False, 40),
        row("fair", "r2", True, 40),
        row("fraud", "r1", False, 0),
        row("fraud", "r2", True, 75),
        row("unknown", "r1", True, 20),
        row("unknown", "r2", True, 20),
    ]
    evidence = harvest.derive_threshold_evidence(rows, 1)
    assert evidence.lower == 40
    assert evidence.upper == 75
    assert evidence.fair_issuers == 1
    assert evidence.fraud_issuers == 1
    assert evidence.unlabeled_issuers == 1


def test_all_rejected_fraud_is_labelled_but_has_no_invented_price():
    rows = [row("fraud", "r1", False, 0), row("fraud", "r2", False, 0)]
    evidence = harvest.derive_threshold_evidence(rows, 1)
    assert evidence.lower == 0
    assert evidence.upper is None
    assert evidence.fraud_issuers == 1
    assert evidence.fraud_issuers_without_price == 1


def test_acceptance_alone_never_labels_threshold():
    rows = [row("x", "r1", True, 999), row("x", "r2", True, 999)]
    evidence = harvest.derive_threshold_evidence(rows, 1)
    assert evidence.lower == 0 and evidence.upper is None
    assert evidence.unlabeled_issuers == 1


def test_mixed_rejection_payments_fail_loudly():
    rows = [row("x", "r1", False, 0), row("x", "r2", False, 10)]
    with pytest.raises(harvest.EvidenceError, match="both paid and unpaid"):
        harvest.derive_threshold_evidence(rows, 1)


def test_actual_score_uses_penalty_only_for_rejected_paid_rows():
    rows = [
        row("Oasis", "x", True, 12),
        row("y", "Oasis", True, 10),
        row("z", "Oasis", False, 20),
        row("w", "Oasis", False, 0),
    ]
    assert harvest.actual_team_score(rows, "Oasis") == {
        "income": 12.0,
        "cost": 40.0,
        "net": -28.0,
    }


def test_archive_path_traversal_is_rejected(tmp_path):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr("../outside.txt", "no")
    with pytest.raises(harvest.HarvestError, match="unsafe"):
        harvest.validate_archive_members(archive)


def test_archive_symlink_is_rejected(tmp_path):
    archive = tmp_path / "link.zip"
    info = zipfile.ZipInfo("link")
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr(info, "target")
    with pytest.raises(harvest.HarvestError, match="symbolic link"):
        harvest.validate_archive_members(archive)


def test_harvester_has_no_submission_code_path():
    source = inspect.getsource(harvest)
    assert ".put(" not in source
    assert "/submissions" not in source


def test_sqlite_cache_remains_compatible_with_threshold_tool(tmp_path):
    from tools.thresholds import brackets

    rows = [
        row("fair", "r1", False, 40),
        row("fair", "r2", True, 40),
        row("fraud", "r1", False, 0),
        row("fraud", "r2", True, 75),
    ]
    path = tmp_path / "cache.sqlite"
    harvest.write_transactions_db(path, 7, rows, ["fair", "fraud", "r1", "r2"])
    connection = harvest.connect(path)
    try:
        result = brackets(connection, game=7)
    finally:
        connection.close()
    assert len(result) == 1
    assert result[0].lo == 40 and result[0].hi == 75
