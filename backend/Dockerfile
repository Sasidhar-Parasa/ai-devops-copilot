# ════════════════════════════════════════════════════════════════
#  AI DevOps Copilot — Backend Dockerfile
#  Fixes:
#  - gcloud config dir permission denied (appuser needs writable home)
#  - gcloud installed system-wide, config dir set via env var
# ════════════════════════════════════════════════════════════════

# ── Stage 1: Builder ─────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends gcc git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: Runtime ─────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Install curl, git, gcloud CLI
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl git gnupg apt-transport-https ca-certificates \
    && echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] \
        https://packages.cloud.google.com/apt cloud-sdk main" \
        | tee /etc/apt/sources.list.d/google-cloud-sdk.list \
    && curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg \
        | gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg \
    && apt-get update && apt-get install -y --no-install-recommends google-cloud-cli \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /install /usr/local

# Copy app
COPY . .

# Create a writable home for appuser + gcloud config dir
RUN useradd -m -u 1000 -s /bin/bash appuser \
    && mkdir -p /home/appuser/.config/gcloud/logs \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /home/appuser /app

# Tell gcloud to use /home/appuser as config root
ENV HOME=/home/appuser
ENV CLOUDSDK_CONFIG=/home/appuser/.config/gcloud

USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8080}/api/ping || exit 1

CMD ["sh", "-c", \
     "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1 --log-level info"]
