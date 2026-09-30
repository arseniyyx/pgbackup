from __future__ import annotations

import shutil
from pathlib import Path


class LocalStorage:
    def __init__(self, base_dir: str | Path) -> None:
        self.base = Path(base_dir)
        self.base.mkdir(parents=True, exist_ok=True)

    def put(self, local_path: str, key: str) -> None:
        dest = self.base / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        if Path(local_path).resolve() != dest.resolve():
            shutil.copy2(local_path, dest)

    def get(self, key: str, local_path: str) -> None:
        src = self.base / key
        if not src.exists():
            raise FileNotFoundError(f"no such backup object: {key}")
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, local_path)

    def list_keys(self, suffix: str = "") -> list[str]:
        if not self.base.exists():
            return []
        return sorted(
            p.name for p in self.base.iterdir() if p.is_file() and p.name.endswith(suffix)
        )

    def delete(self, key: str) -> None:
        (self.base / key).unlink(missing_ok=True)

    def location(self, key: str) -> str:
        return str(self.base / key)
