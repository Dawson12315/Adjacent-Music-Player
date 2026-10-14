# Nginx Proxy Manager (in a container)

[← Back to the README](../../README.md)

NPM is the most common way to publish a self-hosted app, and the most common way
to get stuck. Work through this in order. Steps 3 and 4 of the
[overview](README.md) — closing the other ports and the go-live checklist — still
apply afterwards.

## Why `127.0.0.1` will not work

Every proxy guide on the internet tells you to forward to `127.0.0.1:8000`. That
is correct only when the proxy runs **on the host**. NPM in a container has its
own network namespace, so `127.0.0.1` is *NPM itself*. The connection goes
nowhere and hangs until it times out.

The symptom is distinctive: the page takes 30–60 seconds to load and then shows a
gateway error, or loads the shell and never fetches anything. It looks like a slow
server. It is a proxy talking to itself.

**Containers reach each other by name, on a shared network.** That is what the
`adjacent-net` in the deploy guides is for.

## 1. Put NPM on the same network

```bash
docker network connect adjacent-net <your-npm-container>
```

Confirm all three are on it:

```bash
docker network inspect adjacent-net --format '{{range .Containers}}{{.Name}} {{end}}'
```

You should see `adjacent-backend`, `adjacent-frontend` and your NPM container. If
NPM is missing, nothing below will work.

## 2. Tell Adjacent it lives on a domain

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

## 3. Forward the router's ports to NPM

On your router: forward **TCP 80** and **TCP 443** to the host running NPM.

- Forward only 80 and 443. Never forward 8000 or 5173 — those are the app's own
  ports and have no TLS and no rate limiting in front of them.
- 80 is not optional. Let's Encrypt's HTTP challenge uses it to issue and renew
  your certificate.
- Give the NPM host a static DHCP reservation, or the forward will point at the
  wrong machine after a reboot.

Then point DNS: an `A` record for `music.example.com` at your public IP. On a
dynamic connection use a DDNS provider.

## 4. Create the proxy host

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
| Websockets Support | on |

The forward target is the **container name** and the port **inside** the container
— `8080`, not the `5173` you published on the host. NPM is on the network with it,
so it never touches the published port at all.

Leave **Websockets Support** on: device handoff — moving playback between your phone, the browser and the car — keeps a WebSocket to the backend at `/api/playback/ws`. With it off, handoff still works but falls back to polling, so a change takes a few seconds to show. Caddy and Traefik proxy WebSockets with no extra setting.

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

## 5. Check it

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

## 6. Close the door behind you

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
