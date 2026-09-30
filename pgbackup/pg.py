from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlparse, urlunparse


class PgToolError(RuntimeError):
    pass


def _tool(name: str, pg_bin: str | None) -> str:
    if pg_bin:
        candidate = Path(pg_bin) / name
        if candidate.exists():
            return str(candidate)
    found = shutil.which(name)
    if found:
        return found
    for base in ("/usr/lib/postgresql/16/bin", "/usr/lib/postgresql/15/bin", "/usr/bin"):
        candidate = Path(base) / name
        if candidate.exists():
            return str(candidate)
    raise PgToolError(f"could not find {name}; set pg_bin in config or add it to PATH")


def _split_secret(dsn: str) -> tuple[str, dict[str, str] | None]:
    parsed = urlparse(dsn)
    if not parsed.password:
        return dsn, None
    host = parsed.hostname or ""
    if parsed.port:
        host = f"{host}:{parsed.port}"
    netloc = f"{parsed.username}@{host}" if parsed.username else host
    sanitized = urlunparse(parsed._replace(netloc=netloc))
    return sanitized, {"PGPASSWORD": unquote(parsed.password)}


def _run(cmd: list[str], env: dict[str, str] | None = None) -> str:
    full_env = {**os.environ, **env} if env else None
    proc = subprocess.run(cmd, capture_output=True, text=True, env=full_env)
    if proc.returncode != 0:
        raise PgToolError(f"{cmd[0]} failed: {proc.stderr.strip()}")
    return proc.stdout


def tool_version(pg_bin: str | None, name: str = "pg_dump") -> str:
    out = _run([_tool(name, pg_bin), "--version"])
    return out.strip()


def dump(dsn: str, dest: str, pg_bin: str | None, jobs: int = 1) -> None:
    conn, env = _split_secret(dsn)
    cmd = [_tool("pg_dump", pg_bin), "--format=custom", "--no-owner", "--file", dest, conn]
    _run(cmd, env=env)


def restore(dsn: str, src: str, pg_bin: str | None, jobs: int = 1, clean: bool = False) -> None:
    conn, env = _split_secret(dsn)
    cmd = [_tool("pg_restore", pg_bin), "--no-owner", "--dbname", conn]
    if clean:
        cmd += ["--clean", "--if-exists"]
    if jobs > 1:
        cmd += ["--jobs", str(jobs)]
    cmd.append(src)
    _run(cmd, env=env)


def run_sql(dsn: str, sql: str, pg_bin: str | None) -> str:
    conn, env = _split_secret(dsn)
    return _run([_tool("psql", pg_bin), "--no-psqlrc", "-tAc", sql, conn], env=env)
