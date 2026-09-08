<p align="center">
  <img src="frontend/public/mark.svg" width="96" height="96" alt="Adjacent" />
</p>

<h1 align="center">Adjacent</h1>

<p align="center">
  <strong>Your music library, self-hosted, on every screen you own.</strong>
</p>

<p align="center">
  Point it at a folder of music and get a streaming service: web, iPhone,
  iPad, Android and Android Auto — with your own files, on your own hardware,
  with nobody else's recommendations.
</p>

<p align="center">
  <a href="https://github.com/Dawson12315/Adjacent-Music-Player/actions/workflows/tests.yml">
    <img alt="Tests" src="https://github.com/Dawson12315/Adjacent-Music-Player/actions/workflows/tests.yml/badge.svg" />
  </a>
  <a href="https://github.com/Dawson12315/Adjacent-Music-Player/actions/workflows/docker-publish.yml">
    <img alt="Images" src="https://github.com/Dawson12315/Adjacent-Music-Player/actions/workflows/docker-publish.yml/badge.svg" />
  </a>
  <img alt="Backend" src="https://img.shields.io/badge/backend-FastAPI-009485" />
  <img alt="Frontend" src="https://img.shields.io/badge/frontend-React-61DAFB" />
  <img alt="Mobile" src="https://img.shields.io/badge/mobile-React%20Native-61DAFB" />
</p>

---

## Get started

Two containers and a compose file — you never clone this repo to run it.

```bash
mkdir -p /opt/apps/adjacent && sudo chown -R 1000:1000 /opt/apps/adjacent
# paste the compose file from the Deploy section below
docker compose up -d
```

Then open `http://YOUR_IP:5173`, create the admin account, and press
**Scan library now**.

Full instructions for **[Docker CLI](#docker-cli)**,
**[Portainer](#portainer)**, **[Synology Container
Manager](#synology-container-manager)** and **[Unraid](#unraid)** are below,
along with **[putting it behind a domain with Nginx Proxy
Manager](#nginx-proxy-manager-in-a-container)**.

---

## Clients

| Client | Status | Notes |
|---|---|---|
| **Web** | ✅ Shipped | React app served by the `adjacent-frontend` container. |
| **iOS / iPadOS** | ✅ Shipped | Native app on React Native. Background audio, offline downloads, lock-screen and headset transport. |
| **Android** | ✅ Shipped | Same codebase. Background audio, offline downloads, Android Auto. |
| **CarPlay** | 🚧 Pending | Built; waiting on Apple's CarPlay audio entitlement, which is granted per app on request. |
| **Android Auto** | ✅ Shipped | Media session with transport controls. |
| **watchOS** | 🚧 Planned | Transport control and now-playing on the wrist. |
| **tvOS** | 🚧 Planned | Living-room browse-and-play on the big screen. |

The mobile clients talk to the same server over the same API — sign in with your
server URL and the account you already have.

---

## What it does

**Your library, understood.** Scans a folder of music, reads its tags, and
enriches from MusicBrainz and Last.fm where the tags are thin. Artists, albums
and genres are derived rather than demanded, so a messy library still browses
cleanly.

**Playback that behaves.** Adaptive HLS with a two-rung ladder, or passthrough
for originals. Gapless queueing, shuffle that keeps your current track, repeat,
and a queue you can reorder. Seeking works over a reverse proxy, which is less
common than it should be.

**Offline.** Download a playlist to a phone and it plays with the network off.

**It learns from you, locally.** Listening history drives For You, On Repeat and
Jump Back In. Nothing leaves your server.

**Multi-user when you want it.** Starts on SQLite with zero setup; migrate to
Postgres in place from the Settings screen when you want accounts for other
people, each with their own library view, likes and history.

**Last.fm scrobbling**, if you still keep score.

---

## Deploy

Adjacent ships as two published containers. You never clone this repo to run it —
a compose file is the whole install.

Decide three things first:

| | |
|---|---|
| **Music** | where your library already lives on the host. Mounted read-only; Adjacent never writes to it. |
| **Data** | a new empty directory Adjacent may own: database, uploaded artwork, transcode cache. |
| **Secret** | `openssl rand -hex 32`. The backend refuses to start without one. |

The backend runs as **uid 1000**, so the data directory must be writable by that
uid. Each platform below says how, because the answer differs.

Both containers sit on one Docker network called `adjacent-net`. That is not
decoration: it is what lets a reverse proxy running in a container reach them by
name later. See [Nginx Proxy Manager](#nginx-proxy-manager-in-a-container).

---

### Docker CLI

Paths below are the common Linux convention — change them to match your host.

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
      test: ["CMD", "curl", "-sf", "http://localhost:8000/api/health"]
      interval: 30s
      timeout: 5s
      start_period: 20s
      retries: 3
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

---

### Portainer

Same YAML as the CLI section above — Portainer reads standard compose.

1. **Stacks → Add stack**, name it `adjacent`.
2. Paste the YAML into the web editor.
3. Replace `YOUR_IP`, the secret, and the two volume paths.
4. **Deploy the stack.**

Create the data directory and fix its owner *before* deploying — Portainer will
not do it for you, and the backend cannot create a directory it may not write:

```bash
sudo mkdir -p /opt/apps/adjacent
sudo chown -R 1000:1000 /opt/apps/adjacent
```

**Updating, and the one thing that catches everyone:** Portainer redeploys with
the `:latest` image *it already has locally*. Pressing Update alone will report
success and change nothing.

**Stacks → adjacent → Update the stack → enable "Re-pull image and redeploy" →
Update.** That toggle is the entire difference between an update and a no-op.

To confirm you actually moved:

```bash
docker inspect adjacent-backend --format '{{.Image}}'
```

---

### Synology Container Manager

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
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:8000/api/health"]
      interval: 30s
      timeout: 5s
      start_period: 20s
      retries: 3
    restart: unless-stopped

  frontend:
    image: ghcr.io/dawson12315/adjacent-frontend:latest
    container_name: adjacent-frontend
    networks: [adjacent-net]
    ports:
      - "5173:8080"
    environment:
      - API_BASE_URL=http://YOUR_NAS_IP:8000
    depends_on:
      backend:
        condition: service_healthy
    restart: unless-stopped

networks:
  adjacent-net:
    name: adjacent-net
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

---

### Unraid

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
      test: ["CMD", "curl", "-sf", "http://localhost:8000/api/health"]
      interval: 30s
      timeout: 5s
      start_period: 20s
      retries: 3
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

---

### First run

1. Open the frontend and create the admin account.
2. **Settings → Scan library now.** A large library takes a while; watch the
   counts in the sidebar and refresh.
3. Play something to confirm the music mount and transcoding both work.

If the page loads but nothing signs in, the backend is almost always failing to
write its data directory. `docker logs adjacent-backend` says so plainly, and the
fix is the `chown` from your platform's section.

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
    restart: unless-stopped
```

Generate a real password rather than choosing one by hand:

```bash
openssl rand -hex 24
```

### 2. Migrate from the app

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
      # Trust forwarded client IPs ONLY from your proxy's address, so the login
      # rate limiter sees real clients instead of the proxy. Never "*".
      #
      # 127.0.0.1 is right only for a proxy running on the host. A proxy in a
      # container has its own address — see the Nginx Proxy Manager section for
      # how to find it.
      - FORWARDED_ALLOW_IPS=127.0.0.1
```

and in the frontend environment:

```yaml
      - API_BASE_URL=/
```

`/` rather than the domain: the browser asks whatever origin it loaded from, and
the proxy decides what is API and what is app. A full URL works too, but `/`
cannot go stale when the domain changes. Either way the app is same-origin, so
cookies stay first-party and CORS stops applying. The mobile app points at
`https://music.example.com` and needs no other change.

> Setting up a brand-new install directly on the internet? Also set
> `SETUP_TOKEN=$(openssl rand -hex 16)` on the backend. Without it, whoever
> reaches an install that has no admin yet — a scanner, most likely — can
> claim it. With it, first-run setup asks for that value.

### 2. Put a TLS proxy in front

Pick one. Nginx Proxy Manager is covered in full because it is what most
people run and where most people get stuck; Caddy and nginx follow for anyone
running the proxy on the host rather than in a container.

### Nginx Proxy Manager (in a container)

NPM is the most common way to publish a self-hosted app, and the most common way
to get stuck. Work through this in order.

#### Why `127.0.0.1` will not work

Every proxy guide on the internet tells you to forward to `127.0.0.1:8000`. That
is correct only when the proxy runs **on the host**. NPM in a container has its
own network namespace, so `127.0.0.1` is *NPM itself*. The connection goes
nowhere and hangs until it times out.

The symptom is distinctive: the page takes 30–60 seconds to load and then shows a
gateway error, or loads the shell and never fetches anything. It looks like a slow
server. It is a proxy talking to itself.

**Containers reach each other by name, on a shared network.** That is what the
`adjacent-net` in the deploy section is for.

#### 1. Put NPM on the same network

```bash
docker network connect adjacent-net <your-npm-container>
```

Confirm all three are on it:

```bash
docker network inspect adjacent-net --format '{{range .Containers}}{{.Name}} {{end}}'
```

You should see `adjacent-backend`, `adjacent-frontend` and your NPM container. If
NPM is missing, nothing below will work.

#### 2. Tell Adjacent it lives on a domain

In the **backend** environment:

```yaml
      - FRONTEND_ORIGIN=https://music.example.com
      # TLS exists now, so cookies must be HTTPS-only.
      - AUTH_COOKIE_SECURE=true
      # Trust forwarded client IPs only from NPM. See the note below — the
      # default of 127.0.0.1 is wrong once the proxy is a container.
      - FORWARDED_ALLOW_IPS=172.18.0.0/16
```

In the **frontend** environment:

```yaml
      - API_BASE_URL=/
```

`API_BASE_URL=/` is the whole point of a reverse proxy: the browser asks the same
origin it loaded from, the proxy decides what is API and what is app. Cookies stay
first-party and CORS stops applying. Do not put your domain here — a full URL
works, but `/` cannot go stale when the domain changes.

> **`FORWARDED_ALLOW_IPS` deserves a sentence.** The backend reads
> `X-Forwarded-For` to rate-limit sign-ins by real client IP. It only trusts that
> header from addresses you list, and the default is `127.0.0.1` — which a
> containerised NPM never is. Left alone, every request appears to come from the
> proxy and one person tripping the limiter locks out everyone.
>
> Find the subnet:
>
> ```bash
> docker network inspect adjacent-net --format '{{range .IPAM.Config}}{{.Subnet}}{{end}}'
> ```
>
> Use that value. Never `*` — that would let anyone forge a client IP by sending
> the header themselves.

Redeploy the stack so the new environment takes effect.

#### 3. Forward the router's ports to NPM

On your router: forward **TCP 80** and **TCP 443** to the host running NPM.

- Forward only 80 and 443. Never forward 8000 or 5173 — those are the app's own
  ports and have no TLS and no rate limiting in front of them.
- 80 is not optional. Let's Encrypt's HTTP challenge uses it to issue and renew
  your certificate.
- Give the NPM host a static DHCP reservation, or the forward will point at the
  wrong machine after a reboot.

Then point DNS: an `A` record for `music.example.com` at your public IP. On a
dynamic connection use a DDNS provider.

#### 4. Create the proxy host

**Hosts → Proxy Hosts → Add Proxy Host.**

**Details tab**

| Field | Value |
|---|---|
| Domain Names | `music.example.com` |
| Scheme | `http` |
| Forward Hostname / IP | `adjacent-frontend` |
| Forward Port | `8080` |
| Cache Assets | off |
| Block Common Exploits | on |
| Websockets Support | off |

The forward target is the **container name** and the port **inside** the container
— `8080`, not the `5173` you published on the host. NPM is on the network with it,
so it never touches the published port at all.

**Custom locations tab** — add three, all pointing at the backend:

| Location | Scheme | Forward Hostname / IP | Forward Port |
|---|---|---|---|
| `/api` | `http` | `adjacent-backend` | `8000` |
| `/uploads` | `http` | `adjacent-backend` | `8000` |
| `/legacy-uploads` | `http` | `adjacent-backend` | `8000` |

Miss `/uploads` and the app works but every piece of artwork is broken, because
covers are served by the backend and would otherwise be answered by the frontend
as "not found".

**SSL tab**

- Request a new certificate, **Force SSL** on, **HTTP/2** on, **HSTS** on.
- Agree to the Let's Encrypt terms. Issuance needs port 80 already forwarded.

**Advanced tab** — paste this:

```nginx
client_max_body_size 64m;

# Audio is streamed with Range requests and HLS segments. Buffering makes the
# proxy spool a whole response before sending any of it, which turns seeking
# into a stall.
proxy_buffering off;
proxy_request_buffering off;

proxy_read_timeout 300s;
proxy_send_timeout 300s;
```

`client_max_body_size` is the one people hit: nginx defaults to 1 MB, and any
artwork upload larger than that fails with a 413 that the UI can only report as a
generic error.

If your NPM version shows a **"Trust upstream forwarded proto headers"** toggle,
leave it **off**. NPM is the outermost proxy and sets those headers itself; trusting
what arrives from outside would let a client claim its plain-HTTP request was HTTPS.

#### 5. Check it

```bash
# From the NPM container — proves name resolution and reachability.
docker exec <your-npm-container> curl -sf -o /dev/null -w '%{http_code}\n' \
  http://adjacent-backend:8000/api/health
docker exec <your-npm-container> curl -sf -o /dev/null -w '%{http_code}\n' \
  http://adjacent-frontend:8080/
```

Two `200`s mean the networking is right and anything still broken is NPM
configuration.

Then, in a browser:

1. `https://music.example.com` loads over TLS with a valid certificate.
2. Sign in. In DevTools → Application → Cookies, the session cookie shows
   **Secure** and **HttpOnly**.
3. DevTools → Network: requests go to `music.example.com/api/...`, **not** to
   `http://YOUR_IP:8000`. If you see the raw IP, `API_BASE_URL` did not take —
   redeploy the frontend and hard-refresh.
4. Play a track and drag the scrubber. Seeking exercises Range requests through
   the proxy, which is what `proxy_buffering off` is for.
5. Sign in from the mobile app using `https://music.example.com`.

> **Cache-busting note.** The frontend's JavaScript is cached hard, and Cloudflare
> caches `.js` by extension whether or not you asked it to. If a change refuses to
> appear, purge the CDN and hard-refresh (⇧⌘R / Ctrl-F5). Testing with a
> `?v=2` query string is misleading: a query string is part of the cache key, so
> that URL is uncached and always looks correct while the real one stays stale.

#### 6. Close the door behind you

Only 80 and 443 should be reachable from outside.

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw deny 8000/tcp
sudo ufw deny 5173/tcp
```

Once NPM works, you can stop publishing the app's ports at all — delete both
`ports:` blocks from the compose. NPM reaches the containers over
`adjacent-net`, so nothing needs to be exposed on the host. That is strictly
better than a firewall rule, because there is no port left to protect.

**Docker bypasses ufw for published ports.** Any `ports:` entry inserts routing
*ahead* of ufw, so `ufw deny 8000` does nothing while `8000:8000` is still in your
compose. Either remove the mapping or bind it to loopback: `127.0.0.1:8000:8000`.

Finally, from a phone on mobile data, confirm `http://your-public-ip:8000` and
`:5173` do not answer.

---

### Caddy and nginx (proxy running on the host)

These forward to `127.0.0.1`, which is correct **only** when the proxy runs on
the host rather than in a container. In a container, use the Nginx Proxy
Manager section above — the reasoning there applies to any containerised proxy.

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

Already done if you followed the Nginx Proxy Manager section — this repeats it
for the Caddy and nginx paths.

Only 80 and 443 should be reachable from outside:

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw deny 8000/tcp
sudo ufw deny 5173/tcp
```

**Better than a firewall rule: stop publishing the ports at all.** Once the proxy
reaches the containers over `adjacent-net`, delete both `ports:` blocks from your
compose. A port that was never published needs no rule.

**Docker bypasses ufw for published ports.** Any `ports:` entry inserts routing
*ahead* of ufw, so `ufw deny 8000` does nothing while `8000:8000` is still in
your compose. Remove the mapping, or bind it to loopback —
`127.0.0.1:8000:8000` — as the multi-user section does for Postgres.

### 4. Go-live checklist

1. DNS `A`/`AAAA` record points at your host.
2. Reverse proxy up, certificate issued, `https://music.example.com` loads.
3. Backend env: `FRONTEND_ORIGIN`, `AUTH_COOKIE_SECURE=true`,
   `FORWARDED_ALLOW_IPS` set to your proxy's address.
4. Frontend env: `API_BASE_URL=/`.
5. Redeploy and confirm both containers are healthy.
6. Router forwards only TCP 80 and 443 to the proxy host.
7. Sign in over HTTPS; confirm the session cookie shows `Secure`.
8. Play a track — including a seek — to confirm streaming through the proxy.
9. Sign in from the mobile app against the new URL.
10. Firewall: 80/443 open, 8000/5173 denied or unpublished, 5432 loopback-only.
11. From another network, confirm `http://your-public-ip:8000` and `:5173` do
    not answer.

---

## Local development

The Deploy section above runs the published containers. To run from source, you need
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

## Architecture

```text
  Web browser        iOS / Android        CarPlay / Android Auto
       │                   │                        │
       └───────────────────┴────────────────────────┘
                           │  HTTPS
                  ┌────────┴────────┐
                  │  Reverse proxy  │   TLS, one origin
                  └────────┬────────┘
             /api/*, /uploads/*  │  everything else
                  ┌─────────┐    │    ┌──────────┐
                  │ backend │◄───┴───►│ frontend │
                  │ FastAPI │         │  nginx   │
                  └────┬────┘         └──────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
   SQLite or      Music files     Transcode
   Postgres        (read-only)      cache
```

Two containers. The frontend is a static React build behind nginx; the backend
is FastAPI with ffmpeg for transcoding. Adding a reverse proxy makes the whole
thing same-origin, which is why cookies stay first-party and the mobile clients
need only one URL.

The database starts as SQLite and can migrate to Postgres in place when you
want more than one account. Your music is mounted read-only and is never
written to — everything Adjacent creates lives in its own data directory.

---

## Updating

Images are rebuilt and published on every push to `main`, so updating is a pull.

```bash
docker compose pull
docker compose up -d
```

Per platform:

| | |
|---|---|
| **Portainer** | Stacks → your stack → **Update the stack** → enable **Re-pull image and redeploy**. Without that toggle it redeploys the image it already has and reports success. |
| **Container Manager** | Project → **Build** with *Reset* selected. |
| **Unraid** | Docker tab → the stack's cog → **Compose Pull**, then **Compose Up**. |

Confirm you actually moved:

```bash
docker inspect adjacent-backend --format '{{.Image}}'
```

Compare that digest before and after. If it did not change, neither did your
install — whatever the UI said.

---

## Status

The server and all three clients are in daily use. What follows is what is
actually finished, not what is planned.

### Shipped

**Server** — library scanning with MusicBrainz and Last.fm enrichment,
adaptive HLS streaming, playlists, listening history and recommendations,
multi-user on Postgres with in-place migration, Last.fm scrobbling, Dockerised
deployment and CI/CD to GHCR.

**Web** — full client: browse, search, queue, playlists, insights, admin.

**iOS and Android** — native clients on React Native. Background audio, offline
downloads, generated artwork, listening stats, Android Auto transport, and
lock-screen controls on both.

### Next

- **watchOS** — transport control and now-playing on the wrist.
- **tvOS** — living-room browse-and-play.
- **CarPlay** — the scene is written; it ships once Apple grants the
  `carplay-audio` entitlement.
- Lyrics.
- Song radio — an endless queue seeded from one track.
- Android Auto browse tree, so the car can browse the library rather than only
  control what is already playing.

---

## Good to know

- **Your files are never modified.** The music mount is read-only. Editing a
  track's title or artwork in Adjacent changes Adjacent's database, not the tags
  in your files — so nothing you do here can damage a library you spent years
  tagging.
- **Everything Adjacent creates** — database, uploaded artwork, transcode cache
  — lives in the one data directory you mount. Back that up and you have backed
  up the install.
- **Not a backup tool.** Adjacent streams a library you already keep somewhere
  safe. Keep your own copies of the music.
- Requires Docker and a mounted music library. Built for self-hosted
  environments; see [Exposing Adjacent to the
  internet](#exposing-adjacent-to-the-internet) before putting it on a domain.

---

## Author

Dawson Hudson