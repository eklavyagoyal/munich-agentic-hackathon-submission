#!/usr/bin/env python3
"""Fail if changed source files overlap verbatim with harvested claim text.

Only aggregate counts are printed. Claim text, matching tokens, keys, and per-case
identifiers never leave memory. This is a guard against accidentally committing a
copied invoice row, policy passage, or damage-description passage.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Iterable

from c2f.estimate.interval_model import DEFAULT_DATASET, load_rows


ROOT = Path(__file__).resolve().parent.parent
TEXT_SUFFIXES = {
    ".css", ".html", ".ini", ".js", ".json", ".md", ".py", ".sh",
    ".toml", ".ts", ".tsx", ".txt", ".yaml", ".yml",
}
MAX_CHANGED_FILES = 2_000
MAX_CHANGED_FILE_BYTES = 16 * 1024 * 1024
POLICY_SHINGLE_WORDS = 12
MIN_DESCRIPTION_WORDS = 5


class PrivacyAuditError(RuntimeError):
    pass


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[a-z0-9]+", value.casefold()))


def _signatures(
    rows: Iterable[dict[str, Any]],
) -> tuple[set[tuple[str, ...]], set[tuple[str, ...]]]:
    long_text: set[tuple[str, ...]] = set()
    descriptions: set[tuple[str, ...]] = set()
    for row in rows:
        try:
            features = row["features"]
            policy = features["policy_text"]
            damage = features["damage_description"]
            description = features["description"]
        except (KeyError, TypeError) as exc:
            raise PrivacyAuditError("dataset row lacks required privacy fields") from exc
        if not all(isinstance(value, str) for value in (policy, damage, description)):
            raise PrivacyAuditError("dataset privacy fields must be strings")
        for value in (policy, damage):
            words = _tokens(value)
            long_text.update(
                words[index:index + POLICY_SHINGLE_WORDS]
                for index in range(max(0, len(words) - POLICY_SHINGLE_WORDS + 1))
            )
        description_words = _tokens(description)
        if len(description_words) >= MIN_DESCRIPTION_WORDS:
            descriptions.add(description_words)
    return long_text, descriptions


def scan_files(
    rows: list[dict[str, Any]], paths: Iterable[Path], *, root: Path = ROOT
) -> dict[str, int]:
    claim_shingles, claim_descriptions = _signatures(rows)
    files_scanned = shingle_matches = description_matches = 0
    matching_files = 0
    for path in sorted(set(paths)):
        if path.suffix.lower() not in TEXT_SUFFIXES:
            raise PrivacyAuditError("changed worktree contains a non-text file")
        try:
            resolved = path.resolve(strict=True)
            if not resolved.is_relative_to(root.resolve()):
                raise PrivacyAuditError("changed path resolves outside the repository")
            size = resolved.stat().st_size
            if size > MAX_CHANGED_FILE_BYTES:
                raise PrivacyAuditError("changed text file exceeds the privacy-scan limit")
            words = _tokens(resolved.read_text(encoding="utf-8"))
        except PrivacyAuditError:
            raise
        except (OSError, UnicodeError) as exc:
            raise PrivacyAuditError(
                f"cannot inspect changed source: {type(exc).__name__}"
            ) from exc
        files_scanned += 1
        work_shingles = {
            words[index:index + POLICY_SHINGLE_WORDS]
            for index in range(max(0, len(words) - POLICY_SHINGLE_WORDS + 1))
        }
        file_shingle_matches = len(work_shingles & claim_shingles)
        file_description_matches = 0
        for description in claim_descriptions:
            width = len(description)
            if any(
                words[index:index + width] == description
                for index in range(max(0, len(words) - width + 1))
            ):
                file_description_matches += 1
        shingle_matches += file_shingle_matches
        description_matches += file_description_matches
        matching_files += bool(file_shingle_matches or file_description_matches)
    return {
        "worktree_files_scanned": files_scanned,
        "matching_worktree_files": matching_files,
        "twelve_word_claim_shingle_matches": shingle_matches,
        "exact_item_description_matches": description_matches,
    }


def changed_paths(root: Path = ROOT) -> list[Path]:
    commands = (
        ["git", "diff", "--name-only", "-z"],
        ["git", "diff", "--cached", "--name-only", "-z"],
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
    )
    names: set[str] = set()
    for command in commands:
        try:
            result = subprocess.run(
                command,
                cwd=root,
                capture_output=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise PrivacyAuditError(
                f"cannot enumerate worktree: {type(exc).__name__}"
            ) from exc
        if result.returncode != 0:
            raise PrivacyAuditError("git could not enumerate the changed worktree")
        names.update(
            os.fsdecode(value) for value in result.stdout.split(b"\0") if value
        )
    if len(names) > MAX_CHANGED_FILES:
        raise PrivacyAuditError("changed worktree exceeds the file-count limit")
    return [root / name for name in sorted(names)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    args = parser.parse_args()
    try:
        result = scan_files(load_rows(args.dataset), changed_paths())
    except (PrivacyAuditError, OSError, ValueError) as exc:
        print(json.dumps({"error_class": type(exc).__name__}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 2 if result["matching_worktree_files"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
