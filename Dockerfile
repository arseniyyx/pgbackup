FROM python:3.12-slim-bookworm

# pg_dump / pg_restore / psql, version 16, from the PostgreSQL apt repo so the
# client can dump a modern server (pg_dump's major version must be >= the server's).
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
        -o /etc/apt/trusted.gpg.d/pgdg.asc \
    && echo "deb http://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client-16 \
    && apt-get purge -y curl gnupg && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY pgbackup ./pgbackup
RUN uv sync --frozen --no-dev

ENTRYPOINT ["uv", "run", "pgbackup"]
