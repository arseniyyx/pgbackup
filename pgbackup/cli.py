from __future__ import annotations

import argparse
import sys

from pgbackup.config import Config
from pgbackup.service import BackupService
from pgbackup.storage.local import LocalStorage


def _build_storage(cfg: Config):
    if cfg.s3 is not None:
        from pgbackup.storage.s3 import S3Storage

        return S3Storage(cfg.s3)
    return LocalStorage(cfg.backup_dir)


def _service(args) -> BackupService:
    cfg = Config.load(args.config)
    return BackupService(cfg, storage=_build_storage(cfg))


def cmd_backup(args) -> int:
    svc = _service(args)
    meta = svc.create()
    mb = meta.size_bytes / 1024 / 1024
    print(f"created {meta.name} ({mb:.1f} MB) at {svc.storage.location(meta.filename)}")
    return 0


def cmd_list(args) -> int:
    svc = _service(args)
    metas = svc.list()
    if not metas:
        print("no backups found")
        return 0
    for m in metas:
        mb = m.size_bytes / 1024 / 1024
        print(f"{m.name}  {m.created_at:%Y-%m-%d %H:%M}  {mb:6.1f} MB  {m.sha256[:12]}")
    return 0


def cmd_restore(args) -> int:
    svc = _service(args)
    target = args.target_dsn or svc.cfg.dsn
    meta = svc.restore(args.name, target, clean=args.clean)
    print(f"restored {meta.name} into {_safe(target)}")
    return 0


def cmd_verify(args) -> int:
    svc = _service(args)
    result = svc.verify(args.name)
    print(
        f"{result['name']}: checksum OK, restored {result['restored_tables']} table(s) "
        f"into a scratch database"
    )
    return 0


def cmd_prune(args) -> int:
    svc = _service(args)
    removed = svc.prune()
    if not removed:
        print("nothing to prune")
    else:
        for name in removed:
            print(f"removed {name}")
        print(f"pruned {len(removed)} backup(s)")
    return 0


def _safe(dsn: str) -> str:
    from urllib.parse import urlparse

    p = urlparse(dsn)
    host = p.hostname or ""
    db = p.path.lstrip("/")
    return f"{host}/{db}"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pgbackup", description="PostgreSQL backup manager.")
    p.add_argument("--config", help="path to a YAML config file")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("backup", help="create a new backup").set_defaults(func=cmd_backup)
    sub.add_parser("list", help="list backups").set_defaults(func=cmd_list)

    pr = sub.add_parser("restore", help="restore a backup")
    pr.add_argument("name")
    pr.add_argument("--target-dsn", help="restore into this DSN instead of the source")
    pr.add_argument("--clean", action="store_true", help="drop existing objects first")
    pr.set_defaults(func=cmd_restore)

    pv = sub.add_parser("verify", help="test-restore a backup into a scratch database")
    pv.add_argument("name")
    pv.set_defaults(func=cmd_verify)

    sub.add_parser("prune", help="apply the retention policy").set_defaults(func=cmd_prune)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # noqa: BLE001
        print(f"pgbackup: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
