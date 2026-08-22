import zipfile

import pytest

from tools import audit_real_cases as audit
from tools import audit_worktree_privacy as privacy


def _archive(path, names):
    with zipfile.ZipFile(path, "w") as archive:
        for name in names:
            archive.writestr(name, b"synthetic")


def test_summary_is_aggregate_and_deterministic():
    assert audit._summary([9, 1, 4]) == {
        "count": 3,
        "min": 1.0,
        "median": 4.0,
        "p95": 9.0,
        "max": 9.0,
    }


def test_archive_inventory_accepts_safe_members(tmp_path):
    path = tmp_path / "safe.zip"
    _archive(path, ["document.pdf", "nested/image.png"])
    assert audit._safe_members(path) == (2, 0)


def test_archive_inventory_rejects_parent_and_absolute_members(tmp_path):
    path = tmp_path / "unsafe.zip"
    _archive(path, ["../outside.txt", "/absolute.txt", "safe.txt"])
    assert audit._safe_members(path) == (3, 2)


def test_archive_inventory_rejects_normalized_duplicates(tmp_path):
    path = tmp_path / "duplicate.zip"
    _archive(path, ["nested/item.txt", "nested/./item.txt"])
    assert audit._safe_members(path) == (2, 1)


def test_archive_inventory_rejects_drive_paths_and_case_collisions(tmp_path):
    path = tmp_path / "platform-unsafe.zip"
    _archive(path, ["C:/outside.txt", "Folder/item.txt", "folder/ITEM.txt"])
    assert audit._safe_members(path) == (3, 2)


def test_archive_inventory_rejects_unicode_normalization_collisions(tmp_path):
    path = tmp_path / "unicode-collision.zip"
    _archive(
        path,
        [
            "caf\N{LATIN SMALL LETTER E WITH ACUTE}.txt",
            "cafe\N{COMBINING ACUTE ACCENT}.txt",
        ],
    )
    assert audit._safe_members(path) == (2, 1)


def test_archive_inventory_enforces_resource_bounds(tmp_path, monkeypatch):
    path = tmp_path / "oversized.zip"
    _archive(path, ["large.txt"])
    monkeypatch.setattr(audit, "MAX_MEMBER_UNCOMPRESSED_BYTES", 4)
    assert audit._safe_members(path) == (1, 1)


def test_key_cache_is_strict_and_never_normalizes_secrets(tmp_path):
    path = tmp_path / "keys.json"
    path.write_text('{"1":"synthetic-key"}', encoding="utf-8")
    assert audit._load_key_cache(path) == {1: "synthetic-key"}
    path.write_text('{"01":"synthetic-key"}', encoding="utf-8")
    with pytest.raises(audit.AuditError, match="game identifier"):
        audit._load_key_cache(path)
    path.write_text('{broken', encoding="utf-8")
    with pytest.raises(audit.AuditError, match="unreadable"):
        audit._load_key_cache(path)
    path.write_text('{"1":"first","1":"second"}', encoding="utf-8")
    with pytest.raises(audit.AuditError, match="duplicate JSON field"):
        audit._load_key_cache(path)


@pytest.mark.parametrize("spec", ["", "0", "2-1", "1,,2", "1-a"])
def test_game_selection_rejects_ambiguous_or_unbounded_input(spec):
    with pytest.raises(audit.AuditError):
        audit._parse_games(spec, [1, 2])


def _privacy_row():
    return {
        "features": {
            "policy_text": "one two three four five six seven eight nine ten eleven twelve",
            "damage_description": "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu",
            "description": "synthetic line item description with enough words",
        }
    }


def test_worktree_privacy_scan_reports_only_aggregate_overlap_counts(tmp_path):
    clean = tmp_path / "clean.md"
    clean.write_text("unrelated synthetic source", encoding="utf-8")
    leaked = tmp_path / "leaked.md"
    leaked.write_text(
        "one two three four five six seven eight nine ten eleven twelve\n"
        "synthetic line item description with enough words",
        encoding="utf-8",
    )
    assert privacy.scan_files([_privacy_row()], [clean], root=tmp_path) == {
        "worktree_files_scanned": 1,
        "matching_worktree_files": 0,
        "twelve_word_claim_shingle_matches": 0,
        "exact_item_description_matches": 0,
    }
    result = privacy.scan_files([_privacy_row()], [leaked], root=tmp_path)
    assert result["matching_worktree_files"] == 1
    assert result["twelve_word_claim_shingle_matches"] == 1
    assert result["exact_item_description_matches"] == 1
