# Backing up

[← Back to the README](../README.md)

Everything Adjacent creates — the database, uploaded artwork, the transcode
caches — lives in the one data directory you mount at `/app/data` in the compose
file. Two things make a plain copy of that directory less complete
than it looks: the SQLite database runs in write-ahead-log mode, so the newest
likes, plays and playlist edits can sit in `app.db-wal` until a checkpoint and
a file copier can catch `app.db` mid-checkpoint; and the caches under
`hls_cache/` and `mobile_cache/` are up to 20 GB of files that rebuild
themselves.

**SQLite (the default).** The server writes a consistent copy of the database
every night at 02:45 to `data/backups/app-nightly-<stamp>.db`, using SQLite's
online backup API, and keeps the last seven. It writes another right before
cleanup removes any track (`app-pre-cleanup-*`, last three). Each copy is
complete on its own — no `-wal` sidecar needed — and opens with any SQLite
tool. Point whatever backs up the host (Hyper Backup, rsync, Duplicati…) at
`data/backups/` plus the artwork under `data/`, and exclude `hls_cache/` and
`mobile_cache/`. For a copy right now, while the server runs:

```bash
docker exec adjacent-backend sqlite3 /app/data/app.db \
  ".backup /app/data/backups/app-manual-$(date +%F).db"
```

To restore: stop the stack, replace `data/app.db` with the copy, delete
`data/app.db-wal` and `data/app.db-shm` if present, start again.

**PostgreSQL.** Never copy the `postgres/` directory under your data directory while the container runs;
a live copy restores to a cluster that refuses to start or is quietly
inconsistent. Dump it instead, and exclude that directory from file-level
backups:

```bash
docker exec adjacent-postgres pg_dump -U adjacent adjacent > adjacent-$(date +%F).sql
```

To restore into an empty database: `docker exec -i adjacent-postgres psql -U
adjacent adjacent < adjacent-<date>.sql`.

**Cleanup is careful on its own.** The nightly cleanup marks a track missing
the first time its file cannot be found and only removes it after it has
stayed missing for a week — an unmounted share for a night costs nothing. It
refuses outright when the library folder is empty or holds none of the files
it knows, refuses to remove more than 500 tracks or a fifth of the library
without you confirming from Settings, and takes the backup above first.
