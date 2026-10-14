# Caddy and nginx (proxy running on the host)

[← Back to the README](../../README.md)

These forward to `127.0.0.1`, which is correct **only** when the proxy runs on
the host rather than in a container. In a container, use the [Nginx Proxy
Manager guide](nginx-proxy-manager.md) — the reasoning there applies to any containerised proxy.

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
