# ═══════════════════════════════════════════════════════════
#  AI DevOps Copilot — Production Dockerfile
#  Multi-stage build: builder → runtime (~180MB final)
# ═══════════════════════════════════════════════════════════

# ── Stage 1: Builder ──────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: Runtime ──────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl git \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy installed deps from builder
COPY --from=builder /install /usr/local

# Copy app source
COPY . .

# SQLite data directory
RUN mkdir -p /app/data

# Non-root user
RUN groupadd -r appgroup && useradd -r -g appgroup -s /bin/false appuser \
    && chown -R appuser:appgroup /app

USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8080}/api/ping || exit 1

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1 --log-level info --access-log --no-use-colors"]
