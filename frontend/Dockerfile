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
# It goes *into index.html* rather than into a separate /config.js. A standalone
# .js file is cached independently of the document that loads it, and CDNs cache
# .js by extension — so changing this setting left a stale value being served to
# browsers while the container's own copy was correct, which is close to
# undiagnosable from either end. index.html is the entry document and already
# revalidates on every load, so a value inlined there cannot go stale on its own.
#
# Written via a temp file rather than `sed -i`: this image runs as the
# unprivileged nginx user, which owns the copied *files* but not the directory
# holding them, and `sed -i` needs to create its temp file in that directory.
# Redirecting over an existing file only needs permission on the file.
#
# Never fatal. An earlier version exited when the substitution failed and turned
# a cosmetic problem into a restart loop and an outage. Serving the untouched
# page is safe: config.js then reports an empty base, and over HTTPS the app
# resolves that to same-origin, which is the right answer behind a proxy anyway.
CMD sh -c ' \
  target=/usr/share/nginx/html/index.html; \
  tmp=$(mktemp) || tmp=/tmp/index.html; \
  if sed "s|<script src=\"/config.js\"></script>|<script>window.APP_CONFIG={API_BASE_URL:\"${API_BASE_URL}\"};</script>|" "$target" > "$tmp" \
     && cat "$tmp" > "$target"; then \
    echo "adjacent: API_BASE_URL=${API_BASE_URL:-(unset, will use same origin over HTTPS)}"; \
  else \
    echo "adjacent: WARNING could not inject API_BASE_URL; serving the page as built" >&2; \
  fi; \
  rm -f "$tmp"; \
  nginx -g "daemon off;"'
