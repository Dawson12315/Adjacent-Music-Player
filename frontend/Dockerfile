FROM node:20-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

RUN npm run build

FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD sh -c "echo \"window.APP_CONFIG = { API_BASE_URL: '$API_BASE_URL' };\" > /usr/share/nginx/html/config.js && nginx -g 'daemon off;'"