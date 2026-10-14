# Exposing Adjacent to the internet

[← Back to the README](../../README.md)

The deploy guides describe a LAN install: plain HTTP, ports open on your
network, no TLS. That is fine behind your router and **not** fine on a public
domain. This guide is the safe way to publish it. If you only ever use
Adjacent at home, skip it — nothing here is required for LAN use.

The shape: **one domain, one origin.** A reverse proxy terminates TLS and
routes `/api/*` to the backend and everything else to the frontend. Adjacent
becomes same-origin, so cookies stay first-party and CORS stops mattering.
Ports 8000, 5173 and 5432 are never reachable from the internet.

## 1. Point the app at your domain

In your backend environment:

```yaml
      - FRONTEND_ORIGIN=https://music.example.com
      # Cookies must be HTTPS-only now that TLS exists.
      - AUTH_COOKIE_SECURE=true
      # Trust forwarded client IPs ONLY from your proxy's address, so the login
      # rate limiter sees real clients instead of the proxy. Never "*".
      #
      # A proxy running on the host does NOT arrive as 127.0.0.1: Docker
      # rewrites its traffic, so the backend sees the bridge network's gateway.
      # Find it with
      #   docker network inspect adjacent-net --format '{{range .IPAM.Config}}{{.Gateway}}{{end}}'
      # and put that here (or the whole subnet). A proxy in a container has
      # its own address — see nginx-proxy-manager.md in this folder.
      - FORWARDED_ALLOW_IPS=172.18.0.1
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

**Reaching it away from home without a domain.** A VPN into your network —
Tailscale, WireGuard — works with the plain-http server as it is: on the
phone, sign in with the server's **IP address**, for example
`http://100.101.102.103:8000` on Tailscale or `http://192.168.1.50:8000` over
WireGuard. Either port works on a phone: the web container's (`:5173`, the
address from the browser) or the backend's (`:8000`); https only where a
certificate is actually there, which on a LAN it usually is not. Use the
address, not a name, on any phone — each platform refuses
a different kind of name. iOS refuses plain http to any named host that is not
`.local`, so `http://nas.lan:8000` or a MagicDNS name fails on an iPhone while
the same thing works in a browser. Android cannot look up `.local` names at
all, so `http://nas.local:8000` — the very shape iOS prefers — fails on an
Android phone with "Can't reach your server"; and an Android phone whose
Private DNS is set to a public provider never asks the home router for names
like `nas.lan` either. The IP address works everywhere. iOS also refuses
self-signed certificates, so for https use a certificate from a public
authority, as the proxy guides set up.

> **A LAN address on a phone needs `AUTH_COOKIE_SECURE=false`.** With the
> setting on — which step 2 asks for — the session cookie
> is only ever sent over https, so a sign-in at `http://192.168.1.50:5173` or
> `http://192.168.1.50:8000` succeeds and then every request after it is
> refused. On Android that reads as the server being unreachable, and the app
> says "This server only accepts secure connections" when it can tell. If the
> server has a domain with a certificate, sign the phone in with that domain,
> on the LAN too; keep the setting on. If it does not, the setting must be
> `false` for any phone to sign in over a plain-http LAN address.

> Setting up a brand-new install directly on the internet? Also set
> `SETUP_TOKEN=$(openssl rand -hex 16)` on the backend. Without it, whoever
> reaches an install that has no admin yet — a scanner, most likely — can
> claim it. With it, first-run setup asks for that value.


## 2. Put a TLS proxy in front

Pick one:

- **[Nginx Proxy Manager](nginx-proxy-manager.md)** — covered in full, because it is
  what most people run and where most people get stuck.
- **[Caddy and nginx](caddy-and-nginx.md)** — for a proxy running on the host
  rather than in a container.

Come back here for steps 3 and 4 when the proxy works.


## 3. Close everything else

Already done if you followed the [Nginx Proxy Manager guide](nginx-proxy-manager.md)
— this repeats it for the Caddy and nginx paths.

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
`127.0.0.1:8000:8000` — as the [multi-user guide](../multi-user.md) does for Postgres.

## 4. Go-live checklist

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
