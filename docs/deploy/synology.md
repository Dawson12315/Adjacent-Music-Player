# Deploy on Synology Container Manager

[← Back to the README](../../README.md)

Container Manager calls a compose file a **Project**.

Synology stores shares under `/volume1`, and its files are not owned by uid 1000,
so the `chown` matters more here than anywhere else.

```yaml
services:
  backend:
    image: ghcr.io/dawson12315/adjacent-backend:latest
    container_name: adjacent-backend
    networks: [adjacent-net]
    ports:
      - "8000:8000"
    volumes:
      - /volume1/docker/adjacent:/app/data
      - /volume1/music:/music:ro
    environment:
      - MUSIC_LIBRARY_PATH=/music
      - FRONTEND_ORIGIN=http://YOUR_NAS_IP:5173
      - MUSICBRAINZ_EMAIL=you@example.com
      - AUTH_SECRET_KEY=PASTE_YOUR_GENERATED_SECRET
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
      - API_BASE_URL=http://YOUR_NAS_IP:8000
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

1. **File Station**: make a folder for the data, e.g. `docker/adjacent`.
2. Enable **SSH** (Control Panel → Terminal & SNMP) and hand it to uid 1000:

   ```bash
   sudo chown -R 1000:1000 /volume1/docker/adjacent
   ```

   Skipping this is the single most common Synology failure: the backend starts,
   cannot write its database, and restarts forever.
3. **Container Manager → Project → Create.**
4. Path: the folder from step 1. Source: **Create docker-compose.yml**.
5. Paste the YAML, replace `YOUR_NAS_IP` and the secret, **Next → Done**.

Open `http://YOUR_NAS_IP:5173`.

> **Port 5173 already taken?** Change the left-hand number only — `"5273:8080"` —
> and set `FRONTEND_ORIGIN` to match. The right-hand number is the port *inside*
> the container and never changes. Synology itself uses 5000/5001, so those are
> the ones to avoid.

**Updating:** Project → **Build** with *Reset* selected, or pull first:

```bash
sudo docker compose -f /volume1/docker/adjacent/docker-compose.yml pull
```
