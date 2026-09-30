from datetime import UTC, datetime, timedelta

import pytest

from pgbackup import pg
from pgbackup.config import Config, RetentionConfig
from pgbackup.model import BackupMeta
from pgbackup.service import BackupService, _database_name, _with_database


def _place(config, name, created_at):
    config.backup_dir.mkdir(parents=True, exist_ok=True)
    (config.backup_dir / f"{name}.dump").write_bytes(b"dummy")
    meta = BackupMeta(
        name=name,
        database="db",
        created_at=created_at,
        size_bytes=5,
        sha256="abc",
        pg_dump_version="pg_dump 16",
    )
    (config.backup_dir / f"{name}.json").write_text(meta.model_dump_json())


def test_create_and_list(seeded_db, config):
    svc = BackupService(config)
    meta = svc.create()

    assert meta.size_bytes > 0
    assert len(meta.sha256) == 64
    assert meta.database == _database_name(config.dsn)
    assert (config.backup_dir / meta.filename).exists()
    assert (config.backup_dir / meta.meta_filename).exists()

    listed = svc.list()
    assert [m.name for m in listed] == [meta.name]


def test_verify_roundtrip(seeded_db, config):
    svc = BackupService(config)
    meta = svc.create()

    result = svc.verify(meta.name)
    assert result["checksum_ok"] is True
    assert result["restored_tables"] >= 1


def test_restore_into_fresh_database(seeded_db, config, dsn):
    svc = BackupService(config)
    meta = svc.create()

    admin = _with_database(dsn, "postgres")
    target_name = "pgbackup_restore_test"
    pg.run_sql(admin, f'DROP DATABASE IF EXISTS "{target_name}" WITH (FORCE)', None)
    pg.run_sql(admin, f'CREATE DATABASE "{target_name}"', None)
    try:
        target = _with_database(dsn, target_name)
        svc.restore(meta.name, target)
        count = pg.run_sql(target, "SELECT count(*) FROM widget", None).strip()
        assert int(count) == 50
    finally:
        pg.run_sql(admin, f'DROP DATABASE IF EXISTS "{target_name}" WITH (FORCE)', None)


def test_checksum_mismatch_is_detected(seeded_db, config):
    svc = BackupService(config)
    meta = svc.create()

    dump = config.backup_dir / meta.filename
    dump.write_bytes(dump.read_bytes() + b"corruption")
    with pytest.raises(ValueError, match="checksum mismatch"):
        svc.restore(meta.name, config.dsn)


def test_prune_keeps_recent_by_days(dsn, tmp_path):
    now = datetime(2026, 1, 10, tzinfo=UTC)
    config = Config(
        dsn=dsn,
        backup_dir=tmp_path / "b",
        retention=RetentionConfig(keep_days=7, keep_last=0),
    )
    _place(config, "old", now - timedelta(days=30))
    _place(config, "recent", now - timedelta(days=1))

    removed = BackupService(config).prune(now=now)
    assert removed == ["old"]
    assert {m.name for m in BackupService(config).list()} == {"recent"}


def test_prune_keeps_last_n(dsn, tmp_path):
    now = datetime(2026, 1, 10, tzinfo=UTC)
    config = Config(
        dsn=dsn,
        backup_dir=tmp_path / "b",
        retention=RetentionConfig(keep_days=0, keep_last=2),
    )
    for i in range(5):
        _place(config, f"b{i}", now - timedelta(days=10 + i))

    removed = BackupService(config).prune(now=now)
    assert set(removed) == {"b2", "b3", "b4"}
    assert {m.name for m in BackupService(config).list()} == {"b0", "b1"}
