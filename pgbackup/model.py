from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class BackupMeta(BaseModel):
    name: str
    database: str
    created_at: datetime
    size_bytes: int
    sha256: str
    pg_dump_version: str
    format: str = "custom"

    @property
    def filename(self) -> str:
        return f"{self.name}.dump"

    @property
    def meta_filename(self) -> str:
        return f"{self.name}.json"
