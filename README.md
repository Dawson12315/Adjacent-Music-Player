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
version: "3.9"

services:
  backend:
    image: ghcr.io/dawson12315/adjacent-backend:latest
    container_name: adjacent-backend
    network_mode: "host"
    volumes:
      - /opt/apps/adjacent:/app/data
      - /mnt/media/music:/music:ro
    environment:
      - /mnt/media/music=/music
      - FRONTEND_ORIGIN=http://YOUR_IP:5173
      - MUSICBRAINZ_EMAIL=Your_Music_Brainz_Account_Email
    restart: unless-stopped

  frontend:
    image: ghcr.io/dawson12315/adjacent-frontend:latest
    container_name: adjacent-frontend
    ports:
      - "5173:80"
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

- Update this path if needed, in both backend volumes and environment(must be matching):

`/mnt/media/music`

to wherever your music is stored on your Docker host.

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