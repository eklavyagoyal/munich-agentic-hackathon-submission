"""AES-zip extraction: pyzipper in-process, 7z binary as fallback."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class DecryptError(RuntimeError):
    pass


def extract(archive: Path, password: str, dest: Path) -> list[Path]:
    dest.mkdir(parents=True, exist_ok=True)
    errors = []
    try:
        import pyzipper
        with pyzipper.AESZipFile(archive) as zf:
            zf.setpassword(password.encode())
            zf.extractall(dest)
            return [dest / n for n in zf.namelist() if not n.endswith("/")]
    except Exception as e:  # noqa: BLE001
        errors.append(f"pyzipper: {type(e).__name__}: {e}")
    exe = shutil.which("7z") or shutil.which("7zz")
    if exe:
        proc = subprocess.run([exe, "x", str(archive), f"-p{password}", f"-o{dest}", "-y"],
                              capture_output=True, text=True, timeout=30)
        if proc.returncode == 0:
            return [p for p in dest.rglob("*") if p.is_file()]
        errors.append(f"7z exit {proc.returncode}: {proc.stderr.strip()[:150]}")
    else:
        errors.append("no 7z on PATH")
    raise DecryptError("; ".join(errors))
