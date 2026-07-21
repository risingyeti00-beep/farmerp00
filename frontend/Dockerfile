# ── Stage 1: Build React app ──────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Copy dependency manifests first (for Docker layer caching)
COPY package*.json ./

# Use npm install since no package-lock.json exists in the repo.
# If a lockfile is added in future, switch to: RUN npm ci --omit=dev
RUN npm install

# Copy source and build
COPY . .
RUN npm run build

# ── Stage 2: Nginx production server ────────────────────────────────────────
FROM nginx:stable-alpine

# Create a non-root user for security
RUN adduser -D -u 1000 appuser

# Copy the built frontend
COPY --from=builder /app/dist /usr/share/nginx/html

# Install wget for healthcheck (busybox wget may not support --spider)
RUN apk add --no-cache wget

# Custom nginx config for SPA routing + API proxy
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Ensure nginx can write its temp files as non-root
RUN chown -R appuser:appuser /var/cache/nginx /var/run /usr/share/nginx/html

USER appuser

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
