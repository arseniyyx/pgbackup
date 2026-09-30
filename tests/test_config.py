import pytest

from pgbackup.config import Config


def test_env_dsn_overrides_file(tmp_path, monkeypatch):
    cfg_file = tmp_path / "pgbackup.yml"
    cfg_file.write_text("dsn: postgresql://from-file/db\n")
    monkeypatch.setenv("PGBACKUP_DSN", "postgresql://from-env/db")

    cfg = Config.load(str(cfg_file))
    assert cfg.dsn == "postgresql://from-env/db"


def test_missing_dsn_raises(monkeypatch):
    monkeypatch.delenv("PGBACKUP_DSN", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValueError, match="no DSN"):
        Config.load(None)


def test_file_config_with_s3(tmp_path, monkeypatch):
    monkeypatch.delenv("PGBACKUP_DSN", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    cfg_file = tmp_path / "pgbackup.yml"
    cfg_file.write_text(
        "dsn: postgresql://localhost/db\ns3:\n  bucket: my-bucket\n  prefix: backups/pg\n"
    )
    cfg = Config.load(str(cfg_file))
    assert cfg.s3 is not None
    assert cfg.s3.bucket == "my-bucket"
    assert cfg.s3.prefix == "backups/pg"
