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