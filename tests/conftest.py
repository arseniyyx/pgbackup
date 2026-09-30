import os

import pytest

from pgbackup import pg
from pgbackup.config import Config

DEFAULT_DSN = "postgresql://postgres@localhost:5432/pgbackup_test"


@pytest.fixture
def dsn():
    return os.environ.get("DATABASE_URL") or os.environ.get("PGBACKUP_DSN") or DEFAULT_DSN


@pytest.fixture
def seeded_db(dsn):
    pg.run_sql(dsn, "DROP TABLE IF EXISTS widget", None)
    pg.run_sql(dsn, "CREATE TABLE widget (id serial primary key, name text not null)", None)
    pg.run_sql(
        dsn,
        "INSERT INTO widget (name) SELECT 'w' || g FROM generate_series(1, 50) g",
        None,
    )
    return dsn


@pytest.fixture
def config(dsn, tmp_path):
    return Config(dsn=dsn, backup_dir=tmp_path / "backups")
