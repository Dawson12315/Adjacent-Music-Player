# Deploy with the Docker CLI

[← Back to the README](../../README.md)

Decide the three things in the README's [Deploy](../../README.md#deploy) section first — where the music is, where the data goes, and a secret. Paths below are the common Linux convention — change them to match your host.

```yaml
services:
  backend:
    image: ghcr.io/dawson12315/adjacent-backend:latest
    container_name: adjacent-backend
    networks: [adjacent-net]
    ports:
      - "8000:8000"
    volumes:
      - /opt/apps/adjacent:/app/data
      - /mnt/media/music:/music:ro
    environment:
      - MUSIC_LIBRARY_PATH=/music
      - FRONTEND_ORIGIN=http://YOUR_IP:5173
      - MUSICBRAINZ_EMAIL=you@example.com
      - AUTH_SECRET_KEY=PASTE_YOUR_GENERATED_SECRET
      # Keep false on plain HTTP. Browsers never send Secure cookies to a
      # http:// LAN address, so true here means you can never sign in.
      - AUTH_COOKIE_SECURE=false
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:8000/api/health/live"]
      interval: 30s
      timeout: 5s
      start_period: 20s
      retries: 3
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
    restart: unless-stopped

  frontend:
    image: ghcr.io/dawson12315/adjacent-frontend:latest
    container_name: adjacent-frontend
    networks: [adjacent-net]
    ports:
      - "5173:8080"
    environment:
      - API_BASE_URL=http://YOUR_IP:8000
    depends_on:
      backend:
        condition: service_healthy
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
    restart: unless-stopped

networks:
  adjacent-net:
    name: adjacent-net
```

```bash
sudo mkdir -p /opt/apps/adjacent
sudo chown -R 1000:1000 /opt/apps/adjacent

docker compose up -d
docker compose ps          # both should read healthy / running
```

Open `http://YOUR_IP:5173`.

**Updating:**

```bash
docker compose pull
docker compose up -d
```
