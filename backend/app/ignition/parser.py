from __future__ import annotations

import zipfile
from pathlib import Path


def safe_extract_zip(zip_path: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as z:
        # Zip Slip prevention
        out_root = out_dir.resolve()
        for member in z.infolist():
            dest = (out_dir / member.filename).resolve()
            if not str(dest).startswith(str(out_root)):
                raise ValueError(f"Unsafe zip entry: {member.filename}")
        z.extractall(out_dir)
