# Adjacent 🎧

Adjacent is a self-hosted, Spotify-inspired music streaming web app that lets you stream and manage your personal music library through a modern web interface.

Built with:
- FastAPI (backend)
- React (frontend)
- Docker (deployment)
- GitHub Actions + GHCR (CI/CD)

---

## 🚀 Quick Start (YAML Deployment Only)

Adjacent can be deployed with a single Docker Compose file — no repo clone required.

---

## 1. Create a docker-compose.yml

Create a file called:

docker-compose.yml

---

## 2. Paste this:

version: "3.9"

services:
  backend:
    image: ghcr.io/dawson12315/adjacent-backend:latest
    container_name: adjacent-backend
    ports:
      - "8000:8000"
    volumes:
      - ./adjacent-data:/app/data
      - /mnt/media/music:/music:ro
    environment:
      - /mnt/media/music=/music
      - FRONTEND_ORIGIN=http://YOUR_IP:5173
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


---

## 3. Update values

NOTE: If you change port on frontend, please update backend environment variable, "FRONTEND_ORIGIN", port to match.


Replace:

YOUR_IP

with your server IP (example: 192.168.86.23)

Update this path in volume and environment:

/mnt/media/music

to wherever your music is stored, in respect to your Docker host.

---

## 4. Deploy

Option A — Portainer:
- Go to Stacks
- Click Add Stack
- Paste the YAML
- Deploy

Option B — CLI:

docker compose up -d

---

## 5. Access the app

http://YOUR_IP:5173

---

## ⚙️ Required Setup

You must have a music library available on your host system.

Examples:
- Synology mount → /mnt/media/music
- Local folder → /home/user/music

This gets mounted into the backend container at:

/music

---

## 🧠 Architecture

Browser  
↓  
React Frontend (Nginx)  
↓  
FastAPI Backend  
↓  
SQLite DB + Music Files  

---

## 🔄 Updating

To update to the latest version:

docker compose pull  
docker compose up -d  

---

## 📍 Current Status

Phase 4 — Core App + UI Refinement

Completed:
- Music playback
- Library scanning
- Persistent player UI
- Dockerized deployment
- CI/CD pipeline

In Progress:
- UI polish
- playback improvements

---

## 🧭 Roadmap

Next:
- Playlist artwork system
- Genre tagging + browsing

Future:
- Last.fm integration
- Recommendation engine
- Related artists/songs
- Mobile companion app

---

## 💡 Purpose

Adjacent is built as:
- a self-hosted Spotify alternative
- a full-stack learning project
- a portfolio-ready system with real deployment and CI/CD

---

## ⚠️ Notes

- Requires Docker
- Requires a mounted music library
- Designed for self-hosted environments

---

## 👤 Author

Dawson Hudson