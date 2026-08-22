#!/usr/bin/env python3
"""Read-only aggregate audit of decrypted tournament cases.

This tool intentionally emits no keys, filenames, document text, line descriptions,
policy clauses, image bytes, prompts, or per-case content. It exists to validate
pipeline assumptions against real archives without creating another submit path.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import subprocess
import tempfile
import unicodedata
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Iterable

import pyzipper
from PIL import Image, UnidentifiedImageError

from c2f.estimate.pricebook import GENERIC, match_rate, unit_class
from c2f.ingest import decrypt, parse
from c2f.scheduler import find_archive
from tools.serve import default_cases_dir


ROOT = Path(__file__).resolve().parent.parent
HARVEST_KEYS = ROOT / "data" / "harvest" / "keys.json"
LEGACY_KEYS = ROOT / "data" / "keys.json"
MAX_KEY_CACHE_BYTES = 1_000_000
MAX_KEY_CHARS = 4_096
MAX_SELECTED_GAMES = 1_000
MAX_GAME_ID = 9_999
MAX_ARCHIVE_BYTES = 32 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 64
MAX_MEMBER_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 256 * 1024 * 1024
MAX_COMPRESSION_RATIO = 1_000.0
MIN_RATIO_CHECK_BYTES = 1 * 1024 * 1024
_CURRENCY = re.compile(r"(?:\bEUR\b|\bUSD\b|\bCHF\b|€|\$)", re.IGNORECASE)
_MONEY_SHAPE = re.compile(r"(?<!\w)\d{1,6}(?:[.,]\d{2})(?!\w)")
_NUMBERED_HEADING = re.compile(r"^\s*(?:§\s*)?\d{1,3}(?:[.][\dA-Za-z]+)*[.)]?\s+\S")


class AuditError(RuntimeError):
    """Invalid audit input; messages never contain key or claim content."""


def default_keys_path() -> Path:
    """Prefer the primary harvester cache, then the older replay-tool cache."""
    return HARVEST_KEYS if HARVEST_KEYS.is_file() else LEGACY_KEYS


def _load_key_cache(path: Path) -> dict[int, str]:
    """Load keys strictly without ever returning or logging their values."""

    def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for name, value in pairs:
            if name in result:
                raise AuditError("key cache contains a duplicate JSON field")
            result[name] = value
        return result

    try:
        if path.stat().st_size > MAX_KEY_CACHE_BYTES:
            raise AuditError("key cache exceeds the audit size limit")
        raw = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    except AuditError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AuditError(f"key cache is unreadable: {type(exc).__name__}") from exc
    if not isinstance(raw, dict):
        raise AuditError("key cache must be a JSON object")
    parsed: dict[int, str] = {}
    for raw_game, key in raw.items():
        if not isinstance(raw_game, str) or not re.fullmatch(r"[1-9]\d{0,3}", raw_game):
            raise AuditError("key cache contains an invalid game identifier")
        if (
            not isinstance(key, str)
            or not key
            or len(key) > MAX_KEY_CHARS
            or any(ord(char) < 32 for char in key)
        ):
            raise AuditError("key cache contains an invalid decryption key")
        game_id = int(raw_game)
        if game_id in parsed:
            raise AuditError("key cache contains duplicate normalized game identifiers")
        parsed[game_id] = key
    return parsed


def _summary(values: Iterable[float]) -> dict[str, float | int | None]:
    vals = sorted(float(v) for v in values if math.isfinite(float(v)))
    if not vals:
        return {"count": 0, "min": None, "median": None, "p95": None, "max": None}
    p95_idx = min(len(vals) - 1, math.ceil(0.95 * len(vals)) - 1)
    return {
        "count": len(vals),
        "min": round(vals[0], 3),
        "median": round(statistics.median(vals), 3),
        "p95": round(vals[p95_idx], 3),
        "max": round(vals[-1], 3),
    }


def _safe_members(archive: Path) -> tuple[int, int]:
    if archive.stat().st_size > MAX_ARCHIVE_BYTES:
        raise AuditError("archive exceeds the compressed-size audit limit")
    total = unsafe = 0
    total_uncompressed = 0
    seen: set[str] = set()
    with pyzipper.AESZipFile(archive) as zf:
        for info in zf.infolist():
            raw = info.filename
            total += 1
            total_uncompressed += info.file_size
            normalized = raw.replace("\\", "/")
            member = PurePosixPath(normalized)
            destination = "/".join(part for part in member.parts if part not in ("", "."))
            destination_key = unicodedata.normalize("NFC", destination).casefold()
            unix_mode = (info.external_attr >> 16) & 0o170000
            is_symlink = unix_mode == 0o120000
            compression_ratio = info.file_size / max(info.compress_size, 1)
            if (
                member.is_absolute()
                or bool(re.match(r"^[A-Za-z]:", normalized))
                or ".." in member.parts
                or not destination
                or any(ord(char) < 32 for char in raw)
                or destination_key in seen
                or is_symlink
                or total > MAX_ARCHIVE_MEMBERS
                or info.file_size > MAX_MEMBER_UNCOMPRESSED_BYTES
                or total_uncompressed > MAX_ARCHIVE_UNCOMPRESSED_BYTES
                or (
                    info.file_size >= MIN_RATIO_CHECK_BYTES
                    and compression_ratio > MAX_COMPRESSION_RATIO
                )
            ):
                unsafe += 1
            seen.add(destination_key)
    return total, unsafe


def _pdf_metadata(path: Path) -> tuple[int | None, bool | None]:
    info = subprocess.run(
        ["pdfinfo", str(path)], capture_output=True, text=True, timeout=5, check=False
    )
    pages = None
    if info.returncode == 0:
        match = re.search(r"^Pages:\s*(\d+)\s*$", info.stdout, re.MULTILINE)
        if match:
            pages = int(match.group(1))
    text = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    has_layer = text.returncode == 0 and bool(text.stdout.strip())
    return pages, has_layer


def _parse_games(spec: str | None, held: list[int]) -> list[int]:
    if spec is None:
        selected = held
    else:
        selected = []
        for raw_part in spec.split(","):
            part = raw_part.strip()
            if not re.fullmatch(r"[1-9]\d{0,3}(?:-[1-9]\d{0,3})?", part):
                raise AuditError("games must be a comma-separated list of IDs or ranges")
            if "-" in part:
                lo, hi = (int(value) for value in part.split("-", 1))
                if lo > hi:
                    raise AuditError("game range lower bound exceeds upper bound")
                selected.extend(range(lo, hi + 1))
            else:
                selected.append(int(part))
    games = sorted(set(selected))
    if len(games) > MAX_SELECTED_GAMES or any(
        game < 1 or game > MAX_GAME_ID for game in games
    ):
        raise AuditError("game selection exceeds the audit bounds")
    return games


def audit(keys_path: Path, cases_dir: Path, games_spec: str | None) -> dict:
    key_cache = _load_key_cache(keys_path)
    held = sorted(key_cache)
    games = _parse_games(games_spec, held)

    extensions: Counter[str] = Counter()
    image_formats: Counter[str] = Counter()
    canonical_units: Counter[str] = Counter()
    errors: Counter[str] = Counter()

    archive_member_counts: list[int] = []
    unsafe_members = 0
    file_counts: list[int] = []
    file_bytes: list[int] = []
    pdf_pages: list[int] = []
    invoice_chars: list[int] = []
    policy_chars: list[int] = []
    damage_chars: list[int] = []
    policy_lines: list[int] = []
    policy_paragraphs: list[int] = []
    policy_numbered_headings: list[int] = []
    image_counts: list[int] = []
    image_bytes: list[int] = []
    image_megapixels: list[float] = []
    item_counts: list[int] = []
    quantities: list[float] = []

    opened = parse_success = 0
    cases_with_policy = cases_with_damage = cases_with_images = 0
    pdfs_with_text_layer = pdfs_without_text_layer = 0
    placeholder_rows = total_rows = 0
    recognized_units = specific_pricebook = 0
    invoices_with_currency_marker = invoices_with_money_shapes = 0
    total_currency_markers = total_money_shapes = 0
    money_shape_locations: Counter[str] = Counter()
    placeholder_diagnostics: Counter[str] = Counter()

    for game_id in games:
        key = key_cache.get(game_id)
        archive = find_archive(cases_dir, game_id)
        if key is None:
            errors["missing_key"] += 1
            continue
        if archive is None:
            errors["missing_archive"] += 1
            continue
        try:
            member_count, member_unsafe = _safe_members(archive)
            archive_member_counts.append(member_count)
            unsafe_members += member_unsafe
            if member_unsafe:
                errors["unsafe_archive_member"] += member_unsafe
                continue
        except Exception:  # aggregate type only; never print archive/provider detail
            errors["archive_inventory_failed"] += 1
            continue

        with tempfile.TemporaryDirectory(prefix="c2f-audit-") as temp_name:
            try:
                files = decrypt.extract(archive, key, Path(temp_name))
                opened += 1
            except Exception:
                errors["decrypt_failed"] += 1
                continue

            file_counts.append(len(files))
            for file in files:
                suffix = file.suffix.lower() or "<none>"
                extensions[suffix] += 1
                try:
                    file_bytes.append(file.stat().st_size)
                except OSError:
                    errors["file_stat_failed"] += 1

                if suffix == ".pdf":
                    try:
                        pages, has_layer = _pdf_metadata(file)
                        if pages is not None:
                            pdf_pages.append(pages)
                        if has_layer:
                            pdfs_with_text_layer += 1
                        else:
                            pdfs_without_text_layer += 1
                    except (OSError, subprocess.SubprocessError):
                        errors["pdf_metadata_failed"] += 1

                if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
                    try:
                        with Image.open(file) as image:
                            image_formats[(image.format or "unknown").lower()] += 1
                            width, height = image.size
                            image_megapixels.append(width * height / 1_000_000)
                            image_bytes.append(file.stat().st_size)
                    except (OSError, ValueError, UnidentifiedImageError):
                        errors["image_decode_failed"] += 1

            try:
                case_files = parse.read_files(files)
            except Exception:
                errors["read_files_failed"] += 1
                continue

            invoice_chars.append(len(case_files.invoice_text))
            policy_chars.append(len(case_files.policy))
            damage_chars.append(len(case_files.damage))
            image_counts.append(len(case_files.images))
            cases_with_policy += bool(case_files.policy.strip())
            cases_with_damage += bool(case_files.damage.strip())
            cases_with_images += bool(case_files.images)

            policy_lines.append(len(case_files.policy.splitlines()))
            paragraphs = [p for p in re.split(r"\n\s*\n", case_files.policy) if p.strip()]
            policy_paragraphs.append(len(paragraphs))
            policy_numbered_headings.append(
                sum(bool(_NUMBERED_HEADING.match(line)) for line in case_files.policy.splitlines())
            )

            currency_count = len(_CURRENCY.findall(case_files.invoice_text))
            money_matches = [
                (line, match)
                for line in case_files.invoice_text.splitlines()
                for match in _MONEY_SHAPE.finditer(line)
            ]
            money_shape_count = len(money_matches)
            total_currency_markers += currency_count
            total_money_shapes += money_shape_count
            invoices_with_currency_marker += currency_count > 0
            invoices_with_money_shapes += money_shape_count > 0
            for line, match in money_matches:
                row = parse.ROW.match(line)
                if row is None:
                    money_shape_locations["outside_parsed_rows"] += 1
                    continue
                token = match.group(0).replace(",", ".")
                try:
                    is_qty = math.isclose(float(token), float(row["qty"].replace(",", ".")))
                except ValueError:
                    is_qty = False
                money_shape_locations[
                    "parsed_row_quantity" if is_qty else "parsed_row_other"
                ] += 1

            try:
                items = parse.parse_line_items(case_files.invoice_text)
                parse_success += 1
            except Exception:
                errors["line_parse_failed"] += 1
                continue

            item_counts.append(len(items))
            total_rows += len(items)
            for item in items:
                quantities.append(item.qty)
                placeholder_rows += item.description == "(row not parsed)"
                if item.description == "(row not parsed)":
                    candidates = [
                        line
                        for line in case_files.invoice_text.splitlines()
                        if re.match(rf"^\s*{re.escape(item.pos)}\s+", line)
                    ]
                    if not candidates:
                        placeholder_diagnostics["position_not_on_own_line"] += 1
                    elif any(parse.ROW.match(line) for line in candidates):
                        placeholder_diagnostics["unexpected_parser_disagreement"] += 1
                    else:
                        placeholder_diagnostics["row_shape_not_supported"] += 1
                canonical = unit_class(item.unit) or "unknown"
                canonical_units[canonical] += 1
                recognized_units += canonical != "unknown"
                specific_pricebook += match_rate(item) is not GENERIC

    return {
        "scope": {
            "keys_held": len(held),
            "games_requested": len(games),
            "games_opened": opened,
            "parse_successes": parse_success,
            "errors_by_class": dict(sorted(errors.items())),
        },
        "archives": {
            "archive_count": len(archive_member_counts),
            "member_total": sum(archive_member_counts),
            "member_count": _summary(archive_member_counts),
            "unsafe_archive_members": unsafe_members,
            "file_total": sum(file_counts),
            "files_per_case": _summary(file_counts),
            "file_extensions": dict(sorted(extensions.items())),
            "file_bytes": _summary(file_bytes),
        },
        "modalities": {
            "cases_with_policy": cases_with_policy,
            "cases_with_damage_description": cases_with_damage,
            "cases_with_images": cases_with_images,
            "image_total": sum(image_counts),
            "images_per_case": _summary(image_counts),
            "image_formats": dict(sorted(image_formats.items())),
            "image_bytes": _summary(image_bytes),
            "image_megapixels": _summary(image_megapixels),
            "pdf_pages": _summary(pdf_pages),
            "pdfs_with_text_layer": pdfs_with_text_layer,
            "pdfs_without_text_layer": pdfs_without_text_layer,
        },
        "documents": {
            "invoice_chars": _summary(invoice_chars),
            "policy_chars": _summary(policy_chars),
            "damage_chars": _summary(damage_chars),
            "policy_lines": _summary(policy_lines),
            "policy_paragraphs": _summary(policy_paragraphs),
            "policy_numbered_heading_candidates": _summary(policy_numbered_headings),
        },
        "invoice": {
            "item_count": _summary(item_counts),
            "total_rows": total_rows,
            "placeholder_rows": placeholder_rows,
            "placeholder_rate": round(placeholder_rows / total_rows, 6) if total_rows else None,
            "placeholder_diagnostics": dict(sorted(placeholder_diagnostics.items())),
            "quantity": _summary(quantities),
            "canonical_units": dict(sorted(canonical_units.items())),
            "recognized_unit_rate": round(recognized_units / total_rows, 6) if total_rows else None,
            "specific_pricebook_match_rate": round(specific_pricebook / total_rows, 6)
            if total_rows
            else None,
            "price_presence_heuristics": {
                "invoices_with_currency_markers": invoices_with_currency_marker,
                "total_currency_markers": total_currency_markers,
                "invoices_with_money_shaped_tokens": invoices_with_money_shapes,
                "total_money_shaped_tokens": total_money_shapes,
                "money_shaped_token_locations": dict(sorted(money_shape_locations.items())),
                "warning": "Token shapes are not column-aware and do not prove a stated line price.",
            },
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keys", type=Path, default=default_keys_path())
    parser.add_argument("--cases-dir", type=Path, default=None)
    parser.add_argument("--games", default=None, help="optional aggregate scope, e.g. 1-10 or 1,3")
    args = parser.parse_args()

    cases_dir = args.cases_dir or default_cases_dir()
    result = audit(args.keys, cases_dir, args.games)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not result["scope"]["errors_by_class"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
