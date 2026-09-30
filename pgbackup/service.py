from __future__ import annotations

import hashlib
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from pgbackup import pg
from pgbackup.config import Config
from pgbackup.model import BackupMeta
from pgbackup.storage.local import LocalStorage


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _database_name(dsn: str) -> str:
    parsed = urlparse(dsn)
    name = parsed.path.lstrip("/")
    return name or "postgres"


def _with_database(dsn: str, database: str) -> str:
    parsed = urlparse(dsn)
    return urlunparse(parsed._replace(path=f"/{database}"))


def _timestamp_name(database: str, now: datetime) -> str:
    return f"{database}-{now.strftime('%Y%m%dT%H%M%SZ')}"


class BackupService:
    def __init__(self, cfg: Config, storage=None) -> None:
        self.cfg = cfg
        self.storage = storage or LocalStorage(cfg.backup_dir)

    def create(self, now: datetime | None = None) -> BackupMeta:
        now = now or datetime.now(UTC)
        database = _database_name(self.cfg.dsn)
        name = _timestamp_name(database, now)
        with tempfile.TemporaryDirectory() as tmp:
            dump_path = str(Path(tmp) / f"{name}.dump")
            pg.dump(self.cfg.dsn, dump_path, self.cfg.pg_bin, self.cfg.jobs)
            meta = BackupMeta(
                name=name,
                database=database,
                created_at=now,
                size_bytes=Path(dump_path).stat().st_size,
                sha256=_sha256(dump_path),
                pg_dump_version=pg.tool_version(self.cfg.pg_bin),
            )
            meta_path = str(Path(tmp) / meta.meta_filename)
            Path(meta_path).write_text(meta.model_dump_json(indent=2))
            self.storage.put(dump_path, meta.filename)
            self.storage.put(meta_path, meta.meta_filename)
        return meta

    def list(self) -> list[BackupMeta]:
        metas: list[BackupMeta] = []
        for key in self.storage.list_keys(suffix=".json"):
            with tempfile.TemporaryDirectory() as tmp:
                local = str(Path(tmp) / key)
                self.storage.get(key, local)
                metas.append(BackupMeta.model_validate_json(Path(local).read_text()))
        return sorted(metas, key=lambda m: m.created_at)

    def _fetch_and_check(self, name: str, dest_dir: str) -> tuple[str, BackupMeta]:
        meta_local = str(Path(dest_dir) / f"{name}.json")
        self.storage.get(f"{name}.json", meta_local)
        meta = BackupMeta.model_validate_json(Path(meta_local).read_text())
        dump_local = str(Path(dest_dir) / meta.filename)
        self.storage.get(meta.filename, dump_local)
        actual = _sha256(dump_local)
        if actual != meta.sha256:
            raise ValueError(f"checksum mismatch for {name}: expected {meta.sha256}, got {actual}")
        return dump_local, meta

    def restore(self, name: str, target_dsn: str, clean: bool = False) -> BackupMeta:
        with tempfile.TemporaryDirectory() as tmp:
            dump_local, meta = self._fetch_and_check(name, tmp)
            pg.restore(target_dsn, dump_local, self.cfg.pg_bin, self.cfg.jobs, clean=clean)
        return meta

    def verify(self, name: str) -> dict:
        scratch = f"pgbackup_verify_{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}"
        admin_dsn = _with_database(self.cfg.dsn, "postgres")
        pg.run_sql(admin_dsn, f'CREATE DATABASE "{scratch}"', self.cfg.pg_bin)
        try:
            scratch_dsn = _with_database(self.cfg.dsn, scratch)
            meta = self.restore(name, scratch_dsn)
            tables = pg.run_sql(
                scratch_dsn,
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_schema NOT IN ('pg_catalog', 'information_schema')",
                self.cfg.pg_bin,
            ).strip()
            return {
                "name": name,
                "checksum_ok": True,
                "restored_tables": int(tables or 0),
                "database": meta.database,
            }
        finally:
            pg.run_sql(
                admin_dsn,
                f'DROP DATABASE IF EXISTS "{scratch}" WITH (FORCE)',
                self.cfg.pg_bin,
            )

    def prune(self, now: datetime | None = None) -> list[str]:
        now = now or datetime.now(UTC)
        metas = self.list()
        keep: set[str] = set()

        r = self.cfg.retention
        if r.keep_last > 0:
            for m in metas[-r.keep_last :]:
                keep.add(m.name)
        if r.keep_days > 0:
            cutoff = now.timestamp() - r.keep_days * 86400
            for m in metas:
                if m.created_at.timestamp() >= cutoff:
                    keep.add(m.name)

        removed: list[str] = []
        for m in metas:
            if m.name not in keep:
                self.storage.delete(m.filename)
                self.storage.delete(m.meta_filename)
                removed.append(m.name)
        return removed
