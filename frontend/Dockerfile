FROM node:20-alpine AS build

WORKDIR /app

COPY package*.json ./
# ci, not install: reproducible builds from the committed lockfile.
RUN npm ci

COPY . .

RUN npm run build

# Unprivileged nginx: workers and master both run as the nginx user (uid 101)
# and listen on 8080 instead of 80.
FROM nginxinc/nginx-unprivileged:alpine

COPY --from=build --chown=nginx:nginx /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 8080

# The API base URL is injected at container start, so one image serves any host.
#
# It is written *into index.html* rather than into a separate /config.js. A
# standalone .js file is cached independently of the document that loads it, and
# CDNs cache .js by extension — so changing this setting left a stale value being
# served to browsers while the container's own copy was correct, which is
# extremely hard to see from either end. index.html is the entry document and
# already revalidates on every load, so a value inlined there cannot go stale on
# its own.
#
# The sed target is the tag in index.html; public/config.js stays for `npm run
# dev`, where nothing rewrites anything. Failing loudly if the tag is missing
# beats booting with an unconfigured app.
CMD sh -c 'set -e; \
  target=/usr/share/nginx/html/index.html; \
  grep -q "<script src=\"/config.js\"></script>" "$target" || { \
    echo "FATAL: config script tag not found in index.html" >&2; exit 1; }; \
  sed -i "s|<script src=\"/config.js\"></script>|<script>window.APP_CONFIG={API_BASE_URL:\"${API_BASE_URL}\"};</script>|" "$target"; \
  nginx -g "daemon off;"'
