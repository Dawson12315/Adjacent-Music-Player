# Deploy on Unraid

[← Back to the README](../../README.md)

Unraid has no built-in compose support. Install **Compose Manager** from Community
Applications, or use the Docker tab and add both containers by hand — the compose
route is far less work.

Unraid keeps app data in `/mnt/user/appdata` and shares in `/mnt/user`.

```yaml
services:
  backend:
    image: ghcr.io/dawson12315/adjacent-backend:latest
    container_name: adjacent-backend
    networks: [adjacent-net]
    ports:
      - "8000:8000"
    volumes:
      - /mnt/user/appdata/adjacent:/app/data
      - /mnt/user/media/music:/music:ro
    environment:
      - MUSIC_LIBRARY_PATH=/music
      - FRONTEND_ORIGIN=http://YOUR_TOWER_IP:5173
      - MUSICBRAINZ_EMAIL=you@example.com
      - AUTH_SECRET_KEY=PASTE_YOUR_GENERATED_SECRET
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
      - API_BASE_URL=http://YOUR_TOWER_IP:8000
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

1. **Apps → search "Compose Manager" → Install.**
2. **Docker tab → Add New Stack**, name it `adjacent`.
3. Click the cog → **Edit Stack → Compose File**, paste the YAML, save.
4. From a terminal, create the data directory and give it to uid 1000:

   ```bash
   mkdir -p /mnt/user/appdata/adjacent
   chown -R 1000:1000 /mnt/user/appdata/adjacent
   ```

   Unraid's default owner is `nobody:users` (99:100), which the container cannot
   write to. This step is not optional.
5. **Compose Up.**

Open `http://YOUR_TOWER_IP:5173`.

> **Point `/mnt/user/media/music` at your actual share.** If your music lives in a
> share called `Media` with a `Music` folder, that is `/mnt/user/Media/Music` —
> Unraid share names are case-sensitive here.

**Updating:** Docker tab → the stack's cog → **Compose Pull**, then **Compose Up**.
