# Stage 1: Build the React app
FROM node:20-alpine AS builder

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

COPY frontend/ ./
# Shared config schemas (single source of truth at repo root)
COPY schemas/ /schemas/

RUN npm run build

# Stage 2: Serve with nginx
FROM nginx:1.27-alpine

COPY --from=builder /app/dist /usr/share/nginx/html

# nginx config that handles SPA routing (serves index.html for all routes)
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
