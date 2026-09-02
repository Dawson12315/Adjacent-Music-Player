# Adjacent 🎧

Adjacent is a self-hosted, Spotify-inspired music streaming web app that lets you stream and manage your personal music library through a modern web interface.

Built with:
- FastAPI (backend)
- React (frontend)
- Docker (deployment)
- GitHub Actions + GHCR (CI/CD)

---

## Quick Start (YAML Deployment Only)

Adjacent can be deployed with a single Docker Compose file — no repo clone required.

---

## 1. Create a docker-compose.yml

Create a file called:

`docker-compose.yml`

---

## 2. Paste this:

```yaml
services:
  backend:
    image: ghcr.io/dawson12315/adjacent-backend:latest
    container_name: adjacent-backend
    network_mode: "host"
    volumes:
      - /opt/apps/adjacent:/app/data
      - /mnt/media/music:/music:ro
    environment:
      - MUSIC_LIBRARY_PATH=/music
      - FRONTEND_ORIGIN=http://YOUR_IP:5173
      - MUSICBRAINZ_EMAIL=Your_Music_Brainz_Account_Email
      - AUTH_SECRET_KEY=YOUR_GENERATED_SECRET
      # Keep false unless serving over HTTPS — browsers never send Secure
      # cookies to plain-HTTP LAN addresses, which breaks login.
      - AUTH_COOKIE_SECURE=false
    restart: unless-stopped

  frontend:
    image: ghcr.io/dawson12315/adjacent-frontend:latest
    container_name: adjacent-frontend
    ports:
      - "5173:8080"
    environment:
      - API_BASE_URL=http://YOUR_IP:8000
    depends_on:
      - backend
    restart: unless-stopped
```

---

## 3. Update values

- NOTE: if you change frontend port, you must update port on FRONTEND_ORIGIN in backend environment section of the yaml.

- Replace `YOUR_IP` with your server IP.

Example:

`192.168.86.23`

- Replace `YOUR_GENERATED_SECRET` with your own random secret (required — the backend
  refuses to start without one). Generate it with:

```bash
openssl rand -hex 32
```

- Update this path if needed, in both backend volumes and environment(must be matching):

`/mnt/media/music`

to wherever your music is stored on your Docker host.

- The backend runs as a non-root user (uid 1000). Make sure the data directory on the
  host is writable by that uid — for the example above:

```bash
sudo chown -R 1000:1000 /opt/apps/adjacent
```

---

## 4. Deploy

## 5. Upon Start Up

- Go to settings and press "Scan library now" ~ This may take a while, but status can be seen by watching library stats in sidebar menu and refreshing the page.

### Option A — Portainer

- Go to **Stacks**
- Click **Add stack**
- Paste the YAML
- Deploy

### Option B — CLI

```bash
docker compose up -d
```

---

## 5. Access the app

Open:

`http://YOUR_IP:5173`

---

## Going multi-user (PostgreSQL)

Adjacent starts in single-user mode on SQLite — zero setup, perfect for one
person. Multi-user mode moves the catalog to PostgreSQL and unlocks additional
accounts, each with their own playlists, likes, listening history and
recommendations. The music library itself stays shared.

### 1. Add Postgres to your stack

Paste this alongside the other services in your `docker-compose.yml`, choose a
database password, and `docker compose up -d`:

```yaml
  postgres:
    image: postgres:16-alpine
    container_name: adjacent-postgres
    environment:
      - POSTGRES_DB=adjacent
      - POSTGRES_USER=adjacent
      - POSTGRES_PASSWORD=CHOOSE_A_DB_PASSWORD
    volumes:
      - /opt/apps/adjacent/postgres:/var/lib/postgresql/data
    ports:
      # Loopback only. A bare "5432:5432" publishes the database to every
      # interface — and Docker's port mapping bypasses ufw/firewalld, so a
      # host firewall does NOT protect it. The backend uses host networking,
      # so it reaches Postgres over loopback either way.
      - "127.0.0.1:5432:5432"
    restart: unless-stopped
```

Generate a real password rather than choosing one by hand:

```bash
openssl rand -hex 24
```

### 2. Migrate from the app

As an admin, go to **Settings → Server** and turn on **Multi-user support**.
Fill in the connection — host `localhost` (the backend runs with host
networking, so it reaches the loopback-bound database directly), port `5432`, database `adjacent`,
username `adjacent`, and the password you chose — then press
**Test connection**, and **Migrate & enable**.

What happens next, exactly as the confirmation modal says:

- Adjacent goes read-only for about a minute (playback keeps working).
- Every table is copied to Postgres and verified row-for-row.
- The backend restarts on the new database; everyone stays signed in.
- Your SQLite file is kept untouched at `data/app.db.pre-postgres`.

### 3. Add people

A **Users** section appears under Settings → Server. **+ Add user** generates
a one-time password to hand to them — they choose their own at first sign-in.
Each new account gets its own empty Ducking Good, insights and
recommendations against the shared library.

### Notes

- The switch is one-way from the UI. To return to SQLite: stop the stack,
  delete `data/database.json`, rename `data/app.db.pre-postgres` back to
  `data/app.db`, and start again. Do that with the stack firewalled — an
  install that boots with no database and no admin will let the first caller
  create one.
- Already migrated with `"5432:5432"`? Change it to `"127.0.0.1:5432:5432"`,
  and if you entered a LAN IP as the database host, update
  `data/database.json` to say `localhost` before restarting.
- If Postgres is ever unreachable at boot, the backend retries for ~30
  seconds, then exits with a log message explaining exactly that — it will
  not silently start empty.
- Last.fm scrobbling stays a single global account (the admin's) for now.

---

## Exposing Adjacent to the internet

Everything above describes a LAN install: plain HTTP, ports open on your
network, no TLS. That is fine behind your router and **not** fine on a public
domain. This section is the safe way to publish it. If you only ever use
Adjacent at home, skip it — nothing here is required for LAN use.

The shape: **one domain, one origin.** A reverse proxy terminates TLS and
routes `/api/*` to the backend and everything else to the frontend. Adjacent
becomes same-origin, so cookies stay first-party and CORS stops mattering.
Ports 8000, 5173 and 5432 are never reachable from the internet.

### 1. Point the app at your domain

In your backend environment:

```yaml
      - FRONTEND_ORIGIN=https://music.example.com
      # Cookies must be HTTPS-only now that TLS exists.
      - AUTH_COOKIE_SECURE=true
      # Trust forwarded client IPs ONLY from your proxy's address, so the
      # login rate limiter sees real clients instead of the proxy. Never "*".
      - FORWARDED_ALLOW_IPS=127.0.0.1
```

and in the frontend environment:

```yaml
      - API_BASE_URL=https://music.example.com
```

Same-origin means `API_BASE_URL` is just your domain — the proxy sends
`/api/*` to the backend. The mobile app points at the same URL and needs no
changes.

> Setting up a brand-new install directly on the internet? Also set
> `SETUP_TOKEN=$(openssl rand -hex 16)` on the backend. Without it, whoever
> reaches an install that has no admin yet — a scanner, most likely — can
> claim it. With it, first-run setup asks for that value.

### 2. Put a TLS proxy in front

**Caddy** (gets and renews certificates automatically):

```caddyfile
music.example.com {
	header {
		Strict-Transport-Security "max-age=31536000"
		X-Content-Type-Options "nosniff"
		Referrer-Policy "strict-origin-when-cross-origin"
		Permissions-Policy "camera=(), microphone=(), geolocation=()"
		Content-Security-Policy "frame-ancestors 'none'"
		-Server
	}

	request_body {
		max_size 25MB
	}

	@backend path /api/* /uploads/* /legacy-uploads/*
	handle @backend {
		reverse_proxy 127.0.0.1:8000
	}

	handle {
		reverse_proxy 127.0.0.1:5173
	}
}
```

**nginx** equivalent, with built-in rate limiting:

```nginx
limit_req_zone $binary_remote_addr zone=adjacent_auth:10m rate=10r/m;
limit_req_zone $binary_remote_addr zone=adjacent_api:10m  rate=30r/s;

server {
    listen 80;
    server_name music.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    http2 on;
    server_name music.example.com;

    ssl_certificate     /etc/letsencrypt/live/music.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/music.example.com/privkey.pem;

    add_header Strict-Transport-Security "max-age=31536000" always;
    add_header X-Content-Type-Options nosniff always;
    add_header Referrer-Policy strict-origin-when-cross-origin always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
    add_header Content-Security-Policy "frame-ancestors 'none'" always;

    client_max_body_size 25m;   # artwork uploads; the 1m default would reject them

    location ~ ^/api/auth/(login|recover-password)$ {
        limit_req zone=adjacent_auth burst=5 nodelay;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location ~ ^/(api|uploads|legacy-uploads)(/|$) {
        limit_req zone=adjacent_api burst=60 nodelay;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_buffering off;          # audio Range/HLS: stream, don't spool
        proxy_read_timeout 300s;
    }

    location / {
        proxy_pass http://127.0.0.1:5173;
        proxy_set_header Host $host;
    }
}
```

A useful side effect of routing by path: FastAPI's interactive docs at
`/docs` and `/openapi.json` are not under `/api`, so they never reach the
internet — they stay available to whoever can reach port 8000 directly.

### 3. Close everything else

Only 80 and 443 should be reachable from outside. With the host-networked
backend from the quick-start, ufw governs port 8000 normally:

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw deny 8000/tcp
sudo ufw deny 5173/tcp
```

**Docker caveat:** for containers that publish ports (`ports:` in compose),
Docker inserts its own routing *ahead* of ufw, so `ufw deny 5432` does
nothing. Bind those to loopback in compose instead — `127.0.0.1:5432:5432`,
as the multi-user section above already does.

### 4. Go-live checklist

1. DNS `A`/`AAAA` record points at your host.
2. Reverse proxy up, certificate issued, `https://music.example.com` loads.
3. Backend env: `FRONTEND_ORIGIN`, `AUTH_COOKIE_SECURE=true`,
   `FORWARDED_ALLOW_IPS` set to your proxy's address.
4. Frontend env: `API_BASE_URL=https://music.example.com`.
5. `docker compose up -d` and confirm both containers are healthy.
6. Sign in over HTTPS; confirm the session cookie shows `Secure`.
7. Play a track — including a seek — to confirm streaming through the proxy.
8. Sign in from the mobile app against the new URL.
9. Firewall: 80/443 open, 8000/5173 denied, 5432 loopback-only.
10. From another network, confirm `http://your-ip:8000` and `:5173` do not
    answer.

---

## Local development

The Quick Start above deploys the published containers. To run from source, you need
both services up at once — the web app talks to the API over HTTP, so a web server on
its own just shows "Could not reach the server".

**Both at once (recommended):**

```bash
./scripts/dev.sh
# or, equivalently:
cd frontend && npm run dev:all
```

That starts the API on `:8000` and the web app on `:5173`, prefixes their logs so you
can tell them apart, and stops both on Ctrl+C. Override ports with
`API_PORT=8010 WEB_PORT=5180 ./scripts/dev.sh`.

**Or separately, in two terminals:**

```bash
# Terminal 1 — API
cd backend && .venv/bin/python -m uvicorn app.main:app --reload --port 8000

# Terminal 2 — web app
cd frontend && npm run dev
```

Then open `http://localhost:5173`. Interactive API docs are at `http://localhost:8000/docs`.

### First-time setup

```bash
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cd frontend && npm install
```

`backend/.env` controls the API. `MUSIC_LIBRARY_PATH` must point at a directory that
actually exists, or scanning finds nothing and playback returns 404 for every track —
browsing and insights still work off the indexed database.

### Checks

```bash
cd frontend
npm run test    # unit + integration suite
npm run lint
npm run build
```

### Track durations

Durations are read from file tags during a scan. To fill them in for tracks that were
indexed before that existed:

```bash
cd backend && .venv/bin/python -m app.scripts.backfill_durations
```

It needs the music volume mounted, and skips files it cannot find.

---

## Required Setup

You must have a music library available on your host system.

Examples:
- Synology mount → `/mnt/media/music`
- Local folder → `/home/user/music`

This gets mounted into the container at:

`/music`

---

## Architecture

```text
Browser
   ↓
React Frontend (Nginx)
   ↓
FastAPI Backend
   ↓
SQLite DB + Music Files
```

---

## Updating

```bash
docker compose pull
docker compose up -d
```

---

## Current Status

Phase 5 — Core App + UI Refinement

### Completed
- Music playback
- Library scanning
- Persistent player UI
- Dockerized deployment
- CI/CD pipeline

### In Progress
- UI polish
- Playback improvements

---

## Roadmap

### Next
- Mobile companion app(android)

### Future
- Lyrics
- Song Radio
- Mobile companion app(ios)
- Apple Tv application

---

## Purpose

Adjacent is built as:
- a self-hosted Spotify alternative
- a full-stack learning project
- a portfolio-ready system with real deployment and CI/CD

---

## Notes

- Altering info for music library does not change the music library source metadata, only what is stored in the Adjacent persistent SQLite DB
- Requires Docker
- Requires a mounted music library
- Designed for self-hosted environments

---

## Author

Dawson Hudson