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

# API base URL is injected at container start so one image serves any host.
CMD sh -c "echo \"window.APP_CONFIG = { API_BASE_URL: '$API_BASE_URL' };\" > /usr/share/nginx/html/config.js && nginx -g 'daemon off;'"
