# Going multi-user (PostgreSQL)

[← Back to the README](../README.md)

Adjacent starts in single-user mode on SQLite — zero setup, perfect for one
person. Multi-user mode moves the catalog to PostgreSQL and unlocks additional
accounts, each with their own playlists, likes, listening history and
recommendations. The music library itself stays shared.

## 1. Add Postgres to your stack

Paste this alongside the other services in your `docker-compose.yml`, choose a
database password, and `docker compose up -d`:

```yaml
  postgres:
    image: postgres:16-alpine
    container_name: adjacent-postgres
    networks: [adjacent-net]
    environment:
      - POSTGRES_DB=adjacent
      - POSTGRES_USER=adjacent
      - POSTGRES_PASSWORD=CHOOSE_A_DB_PASSWORD
    volumes:
      - /opt/apps/adjacent/postgres:/var/lib/postgresql/data
    # No `ports:` on purpose. The backend shares adjacent-net and reaches the
    # database by name, so nothing needs to be published to the host at all —
    # which is safer than publishing it and adding a firewall rule, because
    # Docker's port mapping bypasses ufw and firewalld.
    #
    # Only if you want to reach it from the host with psql, add:
    #   ports: ["127.0.0.1:5432:5432"]
    # Loopback-bound. A bare "5432:5432" publishes your database to every
    # interface on the machine.
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
    restart: unless-stopped
```

Generate a real password rather than choosing one by hand:

```bash
openssl rand -hex 24
```

## 2. Migrate from the app

As an admin, go to **Settings → Server** and turn on **Multi-user support**.
Fill in the connection — host `adjacent-postgres` (the container name; the
backend resolves it over `adjacent-net`), port `5432`, database `adjacent`,
username `adjacent`, and the password you chose — then press
**Test connection**, and **Migrate & enable**.

> Use the container name, not `localhost`. `localhost` inside the backend
> container is the backend itself, so the test fails with a connection refused
> that reads like a Postgres problem and is not one.

What happens next, exactly as the confirmation modal says:

- Adjacent goes read-only for about a minute (playback keeps working).
- Every table is copied to Postgres and verified row-for-row.
- The backend restarts on the new database; everyone stays signed in.
- Your SQLite file is kept untouched at `data/app.db.pre-postgres`.

## 3. Add people

A **Users** section appears under Settings → Server. **+ Add user** generates
a one-time password to hand to them — they choose their own at first sign-in.
Each new account gets its own empty Ducking Good, insights and
recommendations against the shared library.

## Notes

- The switch is one-way from the UI. To return to SQLite: stop the stack,
  delete `data/database.json`, rename `data/app.db.pre-postgres` back to
  `data/app.db` — together with `app.db.pre-postgres-wal` and `-shm` if they
  are there, to `app.db-wal` and `app.db-shm` — and start again. Anything
  written on Postgres since the switch stays behind; take a `pg_dump` first if
  you might want it (see [Backing up](backing-up.md)). Do that with the stack
  firewalled — an install that boots with no database and no admin will let
  the first caller create one.
- Re-running the wizard against a database that already holds Adjacent data
  (a previous install, or a long-running one you are trying to return to)
  stops and shows what is there. It only replaces that data if you tick the
  box saying so.
- Already migrated with `"5432:5432"`? Change it to `"127.0.0.1:5432:5432"`,
  and if you entered a LAN IP as the database host, update
  `data/database.json` to say `adjacent-postgres` (the container name, reachable
  over `adjacent-net`) before restarting. Not `localhost`: inside the backend
  container that is the backend itself.
- If Postgres is ever unreachable at boot, the backend retries for ~30
  seconds, then exits with a log message explaining exactly that — it will
  not silently start empty.
- Last.fm scrobbling stays a single global account (the admin's) for now.
