from pgbackup.pg import _split_secret


def test_split_secret_moves_password_to_env():
    conn, env = _split_secret("postgresql://user:s3cret@host:5432/db")
    assert conn == "postgresql://user@host:5432/db"
    assert env == {"PGPASSWORD": "s3cret"}


def test_split_secret_without_password_is_unchanged():
    conn, env = _split_secret("postgresql://user@host:5432/db")
    assert conn == "postgresql://user@host:5432/db"
    assert env is None


def test_split_secret_url_decodes_password():
    conn, env = _split_secret("postgresql://user:p%40ss@host/db")
    assert env == {"PGPASSWORD": "p@ss"}
    assert "p%40ss" not in conn
    assert "p@ss" not in conn
