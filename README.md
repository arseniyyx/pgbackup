# pgbackup

A backup tool for PostgreSQL. It runs `pg_dump` in the custom format, records a small metadata
file next to each dump (size, SHA-256, source database, `pg_dump` version), and keeps the
dumps either on local disk or in S3. It can list what you have, restore a backup, apply a
retention policy, and — the part I care about most — verify a backup by actually restoring it
into a throwaway database.

A backup you've never restored isn't really a backup. `pgbackup verify` catches the dump that
looks fine on disk but won't load.

## Commands

| command | what it does |
|---|---|
| `backup` | dump the source database and store it (with a checksum and metadata) |
| `list` | show stored backups, newest last, with size and checksum |
| `restore <name>` | restore a backup into the source DSN, or into `--target-dsn` |
| `verify <name>` | create a scratch database, restore into it, count the tables, drop it |
| `prune` | delete backups that fall outside the retention policy |

## Install and run

```bash
uv sync
export PGBACKUP_DSN=postgresql://user:pass@localhost:5432/mydb
uv run pgbackup backup
uv run pgbackup list
uv run pgbackup verify mydb-20260930T101500Z
```

`pg_dump`, `pg_restore` and `psql` need to be on `PATH` (or point `pg_bin` at them in the
config). Their major version has to be at least the server's — a 16 client can dump a 15
server, not the other way round.

## Configuration

The connection string comes from `PGBACKUP_DSN` or `DATABASE_URL`, or from a YAML file passed
with `--config`. Everything else lives in the file. See
[`pgbackup.example.yml`](pgbackup.example.yml):

```yaml
dsn: postgresql://user:pass@localhost:5432/mydb
backup_dir: backups
jobs: 2
retention:
  keep_days: 7
  keep_last: 5
s3:
  bucket: my-backups
  prefix: pgbackup
  region: eu-central-1
```

If the `s3` block is present, dumps go to the bucket; otherwise they go to `backup_dir`. The
S3 backend uses the normal AWS credential chain (env vars, `~/.aws`, instance role), and
`endpoint_url` lets you point it at MinIO or another S3-compatible store.

Retention keeps a backup if it is newer than `keep_days` **or** among the last `keep_last`.
Set either to `0` to turn that rule off; with both off, `prune` keeps everything rather than
deleting it.

## How it works

`backup` dumps to a temp file with `pg_dump --format=custom --no-owner`, hashes it, writes a
`<name>.json` metadata file, and hands both files to the storage backend (local or S3). The
name is `<database>-<UTC timestamp>`.

`verify` and `restore` download the dump, re-hash it, and refuse to continue if the checksum
doesn't match what was recorded. `verify` then restores into a fresh `pgbackup_verify_*`
database and drops it in a `finally` block, so a failure part-way through doesn't leave the
scratch database behind.

The password is taken out of the DSN and handed to `pg_dump`/`pg_restore`/`psql` through the
`PGPASSWORD` environment variable instead of the command line, so it doesn't show up in `ps`
or `/proc` while a backup runs.

The storage backend is a small `Protocol` with `put`/`get`/`list_keys`/`delete`, so local disk
and S3 are interchangeable and a new backend (GCS, Azure) is one class.

## Run it locally

`docker-compose.yml` brings up Postgres and runs a backup against it:

```bash
docker compose up --build
```

## Tests

```bash
docker run -d -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=pgbackup_test -p 5432:5432 postgres:16
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/pgbackup_test uv run pytest
```

The service tests do a real `pg_dump` → `pg_restore` round-trip and check the row count in the
restored database; the S3 tests run against a mocked S3 (`moto`), so they need no credentials.

## What I'd add next

- Encryption at rest (age or GPG) before the dump leaves the host.
- WAL archiving and point-in-time recovery, not just nightly full dumps.
- A `--schema-only` / per-table option for partial backups.
- Notifications (a webhook or email) when a scheduled backup or verify fails.
- A small manifest in S3 so `list` doesn't have to read every metadata object.
