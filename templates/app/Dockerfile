FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# The server: API only, production dependencies only.
FROM node:24-alpine AS server
ENV NODE_ENV=production HOST=0.0.0.0 PORT=3000
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev
COPY --from=build /app/dist/src ./dist/src
USER node
CMD ["node", "dist/src/server/main.js"]

# The gateway: the web build, and /api passed to the server.
FROM nginx:1.31.6-alpine AS gateway
COPY --from=build /app/dist/web /usr/share/nginx/html
COPY deploy/nginx.conf.template /etc/nginx/templates/default.conf.template
