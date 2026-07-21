# ── Stage 1: dependency builder ──────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# System libs required by psycopg (libpq) and Pillow (jpeg/zlib)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    libjpeg-dev \
    zlib1g-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: runtime image ────────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Only runtime shared libraries needed (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libjpeg62-turbo \
    zlib1g \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user for security
RUN useradd -m -u 1000 appuser

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy project source (venv2/, media/, db.sqlite3 excluded via .dockerignore)
COPY --chown=appuser:appuser . .

# Collect static files at build time (WhiteNoise serves them at runtime).
# A dummy SECRET_KEY is supplied only for this build step (settings.py requires
# one to import); the real value is injected by Railway at runtime.
RUN SECRET_KEY=build-time-only python manage.py collectstatic --noinput

# NOTE: user-uploaded media goes to Supabase Storage, not local disk, so no
# Docker VOLUME is needed. Railway also rejects the VOLUME instruction
# ("use Railway Volumes"), which fails the build — so it is intentionally omitted.

# Switch to non-root user
USER appuser

EXPOSE 8000

# ── Startup ────────────────────────────────────────────────────────────────
# Run migrations + seed demo data, then start Daphne (HTTP + WebSocket).
# Railway sets $PORT automatically; fall back to 8000 for local Docker.
CMD sh -c "python manage.py migrate --noinput && exec daphne -b 0.0.0.0 -p ${PORT:-8000} config.asgi:application"