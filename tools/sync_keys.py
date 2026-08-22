"""Pull main + keys branch, decrypt any new cases, print a summary.

Usage:
    python tools/sync_keys.py           # pull + decrypt new cases, print summary
    python tools/sync_keys.py --status  # just show what's decrypted vs not, no pull
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
CASES_DIR = ROOT / "data" / "public-cases-ehl" / "cases"
DECRYPT_DIR = ROOT / "data" / "decrypted"


def run(cmd: list[str], check=True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, check=check)


def git_pull_main() -> str:
    r = run(["git", "pull", "origin", "main", "--rebase"], check=False)
    if r.returncode != 0:
        return f"  pull main FAILED: {r.stderr.strip()[:120]}"
    lines = [l for l in r.stdout.splitlines() if l.strip() and "Already up to date" not in l]
    return "  pull main: " + (", ".join(lines) if lines else "already up to date")


def fetch_keys() -> dict[int, str]:
    """Fetch origin/keys and return {game_number: decryption_key}."""
    run(["git", "fetch", "origin", "keys"], check=False)
    r = run(["git", "ls-tree", "origin/keys", "keys/"], check=False)
    if r.returncode != 0:
        return {}
    keys: dict[int, str] = {}
    for line in r.stdout.splitlines():
        # format: 100644 blob <hash>\tkeys/game-NNN.json
        parts = line.split("\t")
        if len(parts) != 2 or not parts[1].endswith(".json") or "README" in parts[1]:
            continue
        fname = parts[1].strip()
        blob = run(["git", "show", f"origin/keys:{fname}"], check=False)
        if blob.returncode != 0:
            continue
        try:
            d = json.loads(blob.stdout)
            keys[int(d["game"])] = d["decryption_key"]
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
    return keys


def decrypt_case(game: int, key: str) -> tuple[bool, str]:
    """Decrypt case_NN.zip if not already done. Returns (is_new, message)."""
    # game N -> case_NN.zip (zero-padded to 2 digits for cases 1-99)
    case_name = f"case_{game:02d}"
    archive = CASES_DIR / f"{case_name}.zip"
    dest = DECRYPT_DIR / case_name

    if not archive.exists():
        return False, f"  {case_name}: archive not found at {archive}"

    # Already decrypted if dest has the expected files
    if dest.exists() and any(dest.iterdir()):
        return False, f"  {case_name}: already decrypted"

    dest.mkdir(parents=True, exist_ok=True)
    exe = None
    for candidate in ["7z", "7zz"]:
        r = subprocess.run(["which", candidate], capture_output=True, text=True)
        if r.returncode == 0:
            exe = r.stdout.strip()
            break
    if exe is None:
        return False, f"  {case_name}: no 7z binary"

    r = subprocess.run(
        [exe, "x", str(archive), f"-p{key}", f"-o{dest}", "-y", "-aoa"],
        capture_output=True, text=True, cwd=ROOT,
    )
    if r.returncode != 0:
        return False, f"  {case_name}: decrypt FAILED — {r.stderr.strip()[:120]}"
    files = [f.name for f in dest.iterdir() if f.is_file()]
    return True, f"  {case_name}: decrypted -> {files}"


def invoice_text(game: int) -> str:
    """Extract invoice text for a game, empty string if unavailable."""
    dest = DECRYPT_DIR / f"case_{game:02d}"
    pdf = dest / "invoices.pdf"
    if not pdf.exists():
        return ""
    r = subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def description_text(game: int) -> str:
    dest = DECRYPT_DIR / f"case_{game:02d}"
    f = dest / "description.txt"
    return f.read_text() if f.exists() else ""


def main(argv: list[str]) -> int:
    status_only = "--status" in argv

    if not status_only:
        print("[ git pull main ]")
        print(git_pull_main())
        print("[ fetching keys branch ]")

    keys = fetch_keys()
    print(f"  keys found: games {sorted(keys)}")

    new_cases: list[int] = []
    print("[ decrypting ]")
    for game in sorted(keys):
        is_new, msg = decrypt_case(game, keys[game])
        print(msg)
        if is_new:
            new_cases.append(game)

    print(f"\n[ summary ] {len(new_cases)} new case(s) decrypted: {new_cases or 'none'}")
    for game in new_cases:
        desc = description_text(game).strip().splitlines()
        inv = invoice_text(game)
        item_lines = [l for l in inv.splitlines() if l.strip() and l[0].isdigit()]
        print(f"\n  case_{game:02d}:")
        print(f"    damage: {desc[0] if desc else '(no description)'}")
        print(f"    ~{len(item_lines)} invoice line items")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
