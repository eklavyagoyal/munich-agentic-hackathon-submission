"""Isolated case decryption worker.

This module imports no ``c2f`` code until after changing into the gitignored runtime
directory. That prevents the package's automatic dotenv loader from looking at the
repository's live configuration file. The parent gives this process a minimal,
credential-free environment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(raw, 0o600)
        os.replace(raw, path)
    finally:
        try:
            os.unlink(raw)
        except FileNotFoundError:
            pass


def _archive_for(root: Path, game: int) -> Path:
    candidates = [
        root / "public-cases-ehl" / "cases" / f"case_{game}.zip",
        root / "public-cases-ehl" / "cases" / f"case_{game:02d}.zip",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError("encrypted case archive unavailable")


def _validate_archive_members(archive: Path) -> None:
    """Reject traversal and symlink members before calling the required extractor."""
    with zipfile.ZipFile(archive) as handle:
        infos = handle.infolist()
        if not infos or len(infos) > 500:
            raise ValueError("archive member count outside safety bounds")
        total = 0
        for info in infos:
            path = Path(info.filename)
            if path.is_absolute() or ".." in path.parts or not info.filename.strip():
                raise ValueError("archive contains an unsafe member path")
            mode = (info.external_attr >> 16) & 0o170000
            if mode == 0o120000:
                raise ValueError("archive contains a symlink")
            total += max(0, info.file_size)
        if total > 750_000_000:
            raise ValueError("archive expanded size exceeds 750 MB")


def _normalise(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]{3,}", text.casefold())
            if token not in {"the", "and", "for", "with", "from", "und", "der", "die", "das"}}


def _page_map(pdf: Path, descriptions: list[str]) -> tuple[int | None, list[int | None]]:
    """Best-effort source-page navigation; never used as a semantic classifier."""
    try:
        proc = subprocess.run(
            ["pdftotext", "-layout", str(pdf), "-"], capture_output=True,
            text=True, timeout=20, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None, [None] * len(descriptions)
    if proc.returncode != 0 or not proc.stdout:
        return None, [None] * len(descriptions)
    pages = proc.stdout.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    page_tokens = [_normalise(page) for page in pages]
    mapping: list[int | None] = []
    for description in descriptions:
        wanted = _normalise(description)
        scores = [len(wanted & tokens) / max(1, len(wanted)) for tokens in page_tokens]
        if not scores or max(scores) < 0.34:
            mapping.append(None)
        else:
            mapping.append(scores.index(max(scores)) + 1)
    return len(pages) or None, mapping


def build(root: Path, runtime: Path, game: int) -> dict[str, Any]:
    root = root.resolve()
    runtime = runtime.resolve()
    expected_runtime = (root / "viz" / "runtime").resolve()
    if runtime != expected_runtime or not _inside(runtime, root / "viz"):
        raise ValueError("runtime must be the repository viz/runtime directory")
    if not 0 <= game <= 100:
        raise ValueError("game outside supported range")
    runtime.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(runtime, 0o700)
    os.chdir(runtime)

    keys_path = root / "data" / "keys.json"
    keys = json.loads(keys_path.read_text(encoding="utf-8"))
    if not isinstance(keys, dict):
        raise ValueError("key cache schema mismatch")
    key = keys.get(str(game))
    if not isinstance(key, str) or not key:
        raise KeyError("decryption key unavailable")
    archive = _archive_for(root, game)
    _validate_archive_members(archive)
    stat = archive.stat()
    version_material = f"{game}:{stat.st_size}:{stat.st_mtime_ns}:".encode() + key.encode()
    version = hashlib.sha256(version_material).hexdigest()[:16]
    manifest_path = runtime / "manifests" / f"game-{game}.json"
    if manifest_path.is_file():
        try:
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
            if existing.get("version") == version:
                return existing
        except (OSError, json.JSONDecodeError):
            pass

    destination = runtime / "cases" / f"game-{game}" / version
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)

    # Delayed import is intentional; cwd has already moved away from the repository
    # configuration file and the parent supplies no credentials in this process.
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from c2f.ingest.decrypt import extract  # pylint: disable=import-outside-toplevel
    from c2f.ingest.parse import build_case  # pylint: disable=import-outside-toplevel

    files = extract(archive, key, destination)
    for path in files:
        if not _inside(path, destination):
            raise ValueError("extractor produced a file outside the runtime case directory")
    case = build_case(f"game-{game}", files)
    pdfs = sorted(path for path in files if path.suffix.casefold() == ".pdf")
    images = sorted(path for path in files if path.suffix.casefold() in {
        ".png", ".jpg", ".jpeg", ".webp", ".gif"
    })
    descriptions = [item.description for item in case.items]
    page_count, page_mapping = (None, [None] * len(descriptions))
    if pdfs:
        page_count, page_mapping = _page_map(pdfs[0], descriptions)

    media: dict[str, dict[str, str]] = {}
    pdf_rows = []
    for number, path in enumerate(pdfs, start=1):
        token = f"pdf-{number}"
        media[token] = {"path": str(path.resolve().relative_to(runtime)), "mime": "application/pdf"}
        pdf_rows.append({"token": token, "name": f"Invoice document {number}"})
    image_rows = []
    mime_by_suffix = {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".webp": "image/webp", ".gif": "image/gif",
    }
    for number, path in enumerate(images, start=1):
        token = f"image-{number}"
        media[token] = {"path": str(path.resolve().relative_to(runtime)),
                        "mime": mime_by_suffix[path.suffix.casefold()]}
        image_rows.append({"token": token, "name": f"Damage photograph {number}"})

    items = []
    for offset, item in enumerate(case.items):
        qty = float(item.qty)
        items.append({
            "idx": int(item.idx), "description": str(item.description),
            "qty": qty if math.isfinite(qty) else None, "unit": str(item.unit),
            "pos": str(item.pos), "trade": str(item.trade or ""),
            "sourcePage": page_mapping[offset] if offset < len(page_mapping) else None,
        })
    manifest = {
        "game": game, "version": version, "policyText": case.policy_text,
        "damageDescription": case.damage_description, "items": items,
        "pdfs": pdf_rows, "images": image_rows, "invoicePageCount": page_count,
        "media": media,
    }
    _atomic_json(manifest_path, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--game", type=int, required=True)
    args = parser.parse_args()
    try:
        manifest = build(args.root, args.runtime, args.game)
    except Exception as exc:  # noqa: BLE001 - boundary converts failure to a safe code
        print(json.dumps({"ok": False, "error": type(exc).__name__}), file=sys.stderr)
        return 2
    print(json.dumps({"ok": True, "game": manifest["game"],
                      "items": len(manifest["items"]), "version": manifest["version"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

