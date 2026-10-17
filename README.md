<p align="center">
  <img src="frontend/public/mark.svg" width="96" height="96" alt="Adjacent" />
</p>

<h1 align="center">Adjacent</h1>

<p align="center">
  <strong>Your music library, self-hosted, on every screen you own.</strong>
</p>

<p align="center">
  Point it at a folder of music and get a streaming service: web, iPhone,
  Android and CarPlay — with your own files, on your own hardware, with
  nobody else's recommendations.
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

## Get started

Two containers and a compose file — you never clone this repo to run it.

1. Make a directory Adjacent may own, for its database, artwork and cache:

   ```bash
   sudo mkdir -p /opt/apps/adjacent && sudo chown -R 1000:1000 /opt/apps/adjacent
   ```

2. Save the compose file from the **[Docker CLI guide](docs/deploy/docker-cli.md)**
   as `docker-compose.yml`. Fill in your host's IP address, the path to your
   music, and a secret from `openssl rand -hex 32`.
3. Start it:

   ```bash
   docker compose up -d
   ```

4. Open `http://YOUR_IP:5173`, create the admin account, and press
   **Settings → Scan library now**.

Step-by-step guides for each platform:
**[Docker CLI](docs/deploy/docker-cli.md)** ·
**[Portainer](docs/deploy/portainer.md)** ·
**[Synology Container Manager](docs/deploy/synology.md)** ·
**[Unraid](docs/deploy/unraid.md)**

Then, when you want them: **[put it on a domain](docs/internet/README.md)**,
**[add more people](docs/multi-user.md)**, **[back it up](docs/backing-up.md)**.

---

## Clients

| Client | Status | Notes |
|---|---|---|
| **Web** | ✅ Shipped | React app served by the `adjacent-frontend` container. |
| **iOS** | ✅ Shipped | Native app on React Native. Background audio, offline downloads, lock-screen and headset transport. iPhone for 1.0 — it runs on an iPad, scaled, but the layout is not designed for one. |
| **Android** | ✅ Shipped | Same codebase. Background audio, offline downloads, notification and lock-screen transport. |
| **CarPlay** | ✅ Shipped | Playlists, albums, artists, recent and search on the car screen, plus Now Playing. Keeps working with the phone screen off. |
| **Android Auto** | ✅ Shipped | The same tree, served to the car by a media browse service. Verified on the Android Automotive emulator; testing on real head units is in progress. |
| **Device handoff** | ✅ Shipped | Playback moves between the browser, the phone and the car. One device plays at a time, and any of them can take over. |
| **watchOS** | 🚧 Planned | Transport control and now-playing on the wrist. |
| **tvOS** | 🚧 Planned | Living-room browse-and-play on the big screen. |

### Signing in on a phone

The apps talk to the same server as the browser. Sign in with the **same
address you open in the browser** — for example `http://192.168.1.50:5173` —
and the account you already have. The web container forwards `/api/` to the
backend, so one address serves both; the backend's own port (`:8000`) works too.

Each platform refuses a different kind of name, so **use the IP address on a
phone** unless the server has a real domain:

| Address you type | Browser | iPhone | Android |
|---|---|---|---|
| `http://192.168.1.50:5173` — an IP address | ✅ | ✅ | ✅ |
| `https://music.example.com` — a domain with a certificate from a public authority | ✅ | ✅ | ✅ |
| `http://nas.local:5173` | ✅ | ✅ | ❌ Android cannot look up `.local` names |
| `http://nas.lan:5173`, a MagicDNS name, any other plain-http name | ✅ | ❌ iOS refuses plain http to a named host | ⚠️ Fails when Private DNS points at a public provider |
| `https://` with a self-signed certificate | ⚠️ After a warning | ❌ | ❌ |

Away from home without a domain, a VPN — Tailscale, WireGuard — works with
the plain-http server as it is. Sign the phone in with the IP address it
sees over the tunnel, for example `http://100.101.102.103:5173`.

> **A LAN address on a phone needs `AUTH_COOKIE_SECURE=false`.** With the
> setting on — which the internet guide asks for — the session cookie is only
> ever sent over https, so a sign-in at `http://192.168.1.50:5173` succeeds and
> then every request after it is refused. On Android that reads as the server
> being unreachable, and the app says "This server only accepts secure
> connections" when it can tell. If the server has a domain with a
> certificate, sign the phone in with that domain, on the LAN too, and keep
> the setting on. If it does not, the setting must be `false` for any phone to
> sign in over a plain-http LAN address.

---

## Deploy

Adjacent ships as two published containers. A compose file is the whole
install. Decide three things first:

| | |
|---|---|
| **Music** | where your library already lives on the host. Mounted read-only; Adjacent never writes to it. |
| **Data** | a new empty directory Adjacent may own: database, uploaded artwork, transcode cache. |
| **Secret** | `openssl rand -hex 32`. The backend refuses to start without one. |

The backend runs as **uid 1000**, so the data directory must be writable by
that uid. Each guide says how, because the answer differs by platform:

| Platform | Guide | What is different there |
|---|---|---|
| Linux, any Docker host | [Docker CLI](docs/deploy/docker-cli.md) | The reference compose file. |
| Portainer | [Portainer](docs/deploy/portainer.md) | Updating needs the **Re-pull image** toggle, or nothing changes. |
| Synology | [Container Manager](docs/deploy/synology.md) | Shares live under `/volume1` and are not owned by uid 1000; the `chown` is essential. |
| Unraid | [Unraid](docs/deploy/unraid.md) | Needs the Compose Manager plugin; appdata is owned by `nobody`. |

Both containers sit on one Docker network called `adjacent-net`. That is not
decoration: it is what lets a reverse proxy running in a container reach them
by name later.

### First run

1. Open the frontend and create the admin account.
2. **Settings → Scan library now.** A large library takes a while; watch the
   counts in the sidebar and refresh.
3. Play something to confirm the music mount and transcoding both work.

Running it for real — one process only, log caps, several addresses, cache
size — is in **[Operating notes](docs/deploy/operating-notes.md)**.

---

## Going further

- **[Exposing Adjacent to the internet](docs/internet/README.md)** — one
  domain, one origin, TLS in front. The shape is a reverse proxy that routes
  `/api/*` to the backend and everything else to the frontend; the backend
  gets `FRONTEND_ORIGIN`, `AUTH_COOKIE_SECURE=true` and `FORWARDED_ALLOW_IPS`,
  the frontend gets `API_BASE_URL=/`, and ports 8000 and 5173 are never
  reachable from outside. Full walkthroughs for
  **[Nginx Proxy Manager](docs/internet/nginx-proxy-manager.md)** and
  **[Caddy or nginx on the host](docs/internet/caddy-and-nginx.md)**, and a
  go-live checklist.
- **[Going multi-user](docs/multi-user.md)** — add Postgres to the stack and
  migrate in place from the Settings screen. Everyone gets their own
  playlists, likes, history and recommendations against the shared library.
- **[Backing up](docs/backing-up.md)** — what the server saves for you every
  night, what to copy, and how to restore on SQLite or Postgres.
- **[Local development](docs/development.md)** — running the API and the web
  app from source.

---

## Troubleshooting

- **The page loads but nobody can sign in.** The backend cannot write its
  data directory. `docker logs adjacent-backend` says so plainly; the fix is
  the `chown -R 1000:1000` from your platform's guide.
- **The browser says "Could not reach the server" right after you changed the
  port or the address.** `FRONTEND_ORIGIN` must match what is in the address
  bar, port included. It takes a comma-separated list if the install is
  opened by more than one name.
- **"Can't reach your server" on a phone, while the browser works.** Three
  causes, in order of likelihood: you typed a name instead of the IP address
  (see the table above); the server has `AUTH_COOKIE_SECURE=true` and you are
  signing in over plain http (set it to `false`, or sign in with the domain);
  or you typed `https://` against a server that has no certificate (use
  `http://`).
- **The phone says "This server only accepts secure connections."**
  `AUTH_COOKIE_SECURE=true` with a plain-http address. Same fix as above.
- **The phone says the address "did not answer like an Adjacent server."**
  You gave it the web app's address on a server whose web image predates the
  `/api/` forward. Update the images, or sign in with the backend's port
  (`http://192.168.1.50:8000`).
- **Behind a proxy, the page takes 30–60 seconds and then shows a gateway
  error.** The proxy runs in a container and forwards to `127.0.0.1`, which
  is the proxy itself. Forward to the container names over `adjacent-net`
  instead; the [Nginx Proxy Manager guide](docs/internet/nginx-proxy-manager.md)
  walks through it.
- **Behind a proxy, every piece of artwork is broken.** The `/uploads`
  location is not forwarded to the backend. Add it next to `/api`.
- **Behind a proxy, seeking stalls or a track takes seconds to start.** The
  proxy is buffering. `proxy_buffering off` for the backend locations.
- **Artwork uploads fail with a generic error.** The proxy's request-size
  limit; nginx defaults to 1 MB. Raise `client_max_body_size`.
- **One person's wrong password locks everyone out.** The backend sees every
  sign-in as coming from the proxy. Set `FORWARDED_ALLOW_IPS` to the proxy's
  address so the rate limiter sees real clients.
- **Device handoff takes a few seconds to notice a change.** The proxy is not
  passing WebSockets. In Nginx Proxy Manager, turn on **Websockets Support**.
- **The scan finds nothing.** The music mount points at the wrong place.
  Check the left-hand side of the `/music:ro` volume; on Unraid, share names
  are case-sensitive.
- **Artists called "01", "07" or "Unknown Artist", usually from a
  soundtrack.** Those files carry no artist tag and are named `07 - Title`.
  The scanner now reads the album artist tag, then the file's name, then its
  folders (`Composer/Album (Year)/Disc 2/07 - Title.flac`), and repairs rows
  it imported that way on its next scan. If a file sits in a folder that
  names nothing, tag it, or move it under `Artist/Album/`.
- **An artist with a single track, by someone else.** The file credits a
  featured artist in its artist tag ("Kodak Black feat. 1900Rugrat"). Both
  are credited, the row names both, and the guest gets a page with that one
  track on it. Edit the tag if the credit is wrong.
- **A compilation or soundtrack shows as one album per performer.** The
  files have no album-artist tag. Set it ("Various Artists", or the
  composer) and the next scan files them as one record; files without the
  tag group on their track artist, as before.
- **`.m4a` files imported with no tags.** Fixed in October 2026; the next
  scan re-reads them. Nothing to do.
- **The backend restarts forever, or `/api/health` says `degraded`.** The
  health endpoint names the missing piece: the library mount, the database or
  ffmpeg. `docker logs adjacent-backend` has the detail.
- **Postgres "Test connection" is refused.** The host is `localhost`, which
  inside the backend container is the backend itself. Use the container name,
  `adjacent-postgres`.
- **An update reported success and changed nothing.** Portainer redeploys the
  image it already has. See [Updating](#updating).

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

## Architecture

```text
  Web browser        iOS / Android              Car screens  
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

## Status

The server and all three clients are in daily use. What follows is what is
actually finished, not what is planned.

### Shipped

**Server** — library scanning with MusicBrainz and Last.fm enrichment,
adaptive HLS streaming, playlists, listening history and recommendations,
multi-user on Postgres with in-place migration, Last.fm scrobbling, device
handoff, Dockerised deployment and CI/CD to GHCR.

**Web** — full client: browse, search, queue, playlists, insights, admin.

**iOS and Android** — native clients on React Native. Background audio, offline
downloads, generated artwork, listening stats and lock-screen controls on both;
CarPlay on iOS and Android Auto on Android.

### Next

- **watchOS** — transport control and now-playing on the wrist.
- **tvOS** — living-room browse-and-play.
- Lyrics.
- Song radio — an endless queue seeded from one track.

---

## Good to know

- **Your files are never modified.** The music mount is read-only. Editing a
  track's title or artwork in Adjacent changes Adjacent's database, not the tags
  in your files — so nothing you do here can damage a library you spent years
  tagging.
- **Everything Adjacent creates** — database, uploaded artwork, transcode cache
  — lives in the one data directory you mount. See
  [Backing up](docs/backing-up.md) for what to copy and how.
- **Not a backup tool.** Adjacent streams a library you already keep somewhere
  safe. Keep your own copies of the music.
- Requires Docker and a mounted music library. Built for self-hosted
  environments; see [Exposing Adjacent to the
  internet](docs/internet/README.md) before putting it on a domain.

---

## Author

Dawson Hudson
