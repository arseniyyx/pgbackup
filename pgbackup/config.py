from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class RetentionConfig(BaseModel):
    keep_days: int = Field(default=7, ge=0)
    keep_last: int = Field(default=0, ge=0)


class S3Config(BaseModel):
    bucket: str
    prefix: str = "pgbackup"
    region: str | None = None
    endpoint_url: str | None = None


class Config(BaseModel):
    dsn: str
    backup_dir: Path = Path("backups")
    pg_bin: str | None = None
    jobs: int = Field(default=2, ge=1, le=32)
    retention: RetentionConfig = RetentionConfig()
    s3: S3Config | None = None

    @classmethod
    def load(cls, path: str | None) -> Config:
        data: dict = {}
        if path:
            data = yaml.safe_load(Path(path).read_text()) or {}
        env_dsn = os.environ.get("PGBACKUP_DSN") or os.environ.get("DATABASE_URL")
        if env_dsn:
            data["dsn"] = env_dsn
        if "PGBACKUP_BACKUP_DIR" in os.environ:
            data["backup_dir"] = os.environ["PGBACKUP_BACKUP_DIR"]
        if not data.get("dsn"):
            raise ValueError("no DSN configured (set dsn in config or PGBACKUP_DSN)")
        return cls.model_validate(data)
