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
      # The web container forwards /api/ from its fixed address; trusting it
      # lets the sign-in limiter see each phone and browser as itself. Behind
      # a reverse proxy, add the proxy's address too, comma-separated.
      - FORWARDED_ALLOW_IPS=172.28.0.3
      # The zone scheduled jobs run in (the scan time in Settings). Set yours.
      - TZ=UTC
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
    networks:
      adjacent-net:
        ipv4_address: 172.28.0.3
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
    # A fixed subnet, so the web container keeps the address the backend
    # trusts for forwarded client addresses (see FORWARDED_ALLOW_IPS).
    ipam:
      config:
        - subnet: 172.28.0.0/24
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
