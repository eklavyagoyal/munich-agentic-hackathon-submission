"""Archive decryption.

pyzipper handles AES-encrypted zips in-process, which removes a subprocess
spawn from the hot path and drops the hard dependency on the `7z` binary.
7-Zip stays as a fallback because GAME_DESCRIPTION's starter script uses it and
we cannot yet confirm the exact archive format (see PIPELINE.md §9).
"""
from __future__ import annotations

import shutil
import subprocess
import zipfile
from pathlib import Path


class DecryptError(RuntimeError):
    pass


def _extract_pyzipper(archive: Path, password: str, dest: Path) -> list[Path]:
    import pyzipper

    try:
        with pyzipper.AESZipFile(archive) as zf:
            zf.setpassword(password.encode())
            zf.extractall(dest)
            return [dest / n for n in zf.namelist() if not n.endswith("/")]
    except Exception as e:  # noqa: BLE001
        raise DecryptError(f"pyzipper: {type(e).__name__}: {e}") from e


def _extract_7z(archive: Path, password: str, dest: Path) -> list[Path]:
    exe = shutil.which("7z") or shutil.which("7zz")
    if exe is None:
        raise DecryptError("no 7z binary on PATH (brew install p7zip)")
    proc = subprocess.run(
        [exe, "x", str(archive), f"-p{password}", f"-o{dest}", "-y"],
        capture_output=True, text=True, timeout=20,
    )
    if proc.returncode != 0:
        raise DecryptError(f"7z exit {proc.returncode}: {proc.stderr.strip()[:200]}")
    return [p for p in dest.rglob("*") if p.is_file()]


def extract(archive: Path, password: str, dest: Path) -> list[Path]:
    """Try in-process first, fall back to the binary. Raises DecryptError."""
    dest.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    for fn in (_extract_pyzipper, _extract_7z):
        try:
            files = fn(archive, password, dest)
            if files:
                return sorted(files)
            errors.append(f"{fn.__name__}: produced no files")
        except DecryptError as e:
            errors.append(str(e))
    raise DecryptError(" | ".join(errors))


def verify_archive(archive: Path) -> bool:
    """Cold-path check: is this a well-formed archive at all?

    A corrupt download found at T+1s is a lost round; the same discovery at
    T-5min is a re-download. We probe with a deliberately wrong password: a
    healthy archive answers 'wrong password', a broken one answers otherwise.
    """
    try:
        with zipfile.ZipFile(archive) as zf:
            return bool(zf.namelist()) and zf.testzip() is None
    except RuntimeError:
        return True          # "encrypted, password required" -- structurally fine
    except (zipfile.BadZipFile, OSError):
        return False
