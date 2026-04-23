#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════
#  AI DevOps Copilot — One-Click GCP Deployment
#  Supports: Groq API, Gemini API, or rule-based fallback
# ═══════════════════════════════════════════════════════════
set -euo pipefail

# ── Config (set these or export them before running) ───────
PROJECT_ID="${GCP_PROJECT_ID:-}"
REGION="${GCP_REGION:-us-central1}"
GROQ_API_KEY="${GROQ_API_KEY:-}"
GEMINI_API_KEY="${GEMINI_API_KEY:-}"

if [[ -z "$PROJECT_ID" ]]; then
  echo "❌ GCP_PROJECT_ID is not set. Run: export GCP_PROJECT_ID=your-project-id"
  exit 1
fi

REPO="$REGION-docker.pkg.dev/$PROJECT_ID/copilot"
BACKEND_IMAGE="$REPO/backend:latest"
FRONTEND_IMAGE="$REPO/frontend:latest"
BACKEND_SVC="ai-copilot-backend"
FRONTEND_SVC="ai-copilot-frontend"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo ""
echo "╔═══════════════════════════════════════════════╗"
echo "║    AI DevOps Copilot — GCP Deployment         ║"
echo "╚═══════════════════════════════════════════════╝"
echo "  Project : $PROJECT_ID"
echo "  Region  : $REGION"
echo "  LLM     : ${GROQ_API_KEY:+Groq}${GEMINI_API_KEY:+Gemini}${GROQ_API_KEY:-${GEMINI_API_KEY:-rule-based}}"
echo ""

# ── Step 1: Auth + APIs ───────────────────────────────────
echo "▶ [1/7] Authenticating..."
gcloud config set project "$PROJECT_ID" --quiet
gcloud config set run/region "$REGION" --quiet

echo "▶ [2/7] Enabling GCP APIs..."
gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com --quiet

# ── Step 2: Artifact Registry ─────────────────────────────
echo "▶ [3/7] Setting up Artifact Registry..."
gcloud artifacts repositories create copilot \
  --repository-format=docker \
  --location="$REGION" \
  --quiet 2>/dev/null || true
gcloud auth configure-docker "$REGION-docker.pkg.dev" --quiet

# ── Step 3: Build backend ─────────────────────────────────
echo "▶ [4/7] Building backend image via Cloud Build..."
cd "$ROOT/backend"
gcloud builds submit --tag "$BACKEND_IMAGE" --timeout=600 --quiet .
echo "   ✅ Backend image ready"

# ── Step 4: Deploy backend ────────────────────────────────
echo "▶ [5/7] Deploying backend to Cloud Run..."
ENV_VARS="LOG_LEVEL=INFO,GCP_PROJECT_ID=$PROJECT_ID,GCP_REGION=$REGION"
[[ -n "$GROQ_API_KEY" ]]   && ENV_VARS="$ENV_VARS,GROQ_API_KEY=$GROQ_API_KEY"
[[ -n "$GEMINI_API_KEY" ]] && ENV_VARS="$ENV_VARS,GEMINI_API_KEY=$GEMINI_API_KEY"

gcloud run deploy "$BACKEND_SVC" \
  --image "$BACKEND_IMAGE" \
  --platform managed --region "$REGION" \
  --allow-unauthenticated \
  --memory 512Mi --cpu 1 \
  --min-instances 0 --max-instances 5 \
  --port 8080 \
  --set-env-vars "$ENV_VARS" \
  --quiet

BACKEND_URL=$(gcloud run services describe "$BACKEND_SVC" \
  --region "$REGION" --format="value(status.url)")
echo "   ✅ Backend: $BACKEND_URL"

# ── Step 5: Build + deploy frontend ───────────────────────
echo "▶ [6/7] Building frontend image..."
cd "$ROOT/frontend"
gcloud builds submit \
  --tag "$FRONTEND_IMAGE" \
  --timeout=600 \
  --substitutions="_VITE_API_URL=${BACKEND_URL}/api" \
  --quiet .
echo "   ✅ Frontend image ready"

echo "▶ [7/7] Deploying frontend to Cloud Run..."
gcloud run deploy "$FRONTEND_SVC" \
  --image "$FRONTEND_IMAGE" \
  --platform managed --region "$REGION" \
  --allow-unauthenticated \
  --memory 256Mi --cpu 1 \
  --min-instances 0 --max-instances 3 \
  --port 8080 \
  --quiet

FRONTEND_URL=$(gcloud run services describe "$FRONTEND_SVC" \
  --region "$REGION" --format="value(status.url)")

# ── Done ──────────────────────────────────────────────────
echo ""
echo "╔═══════════════════════════════════════════════╗"
echo "║          🚀 Deployment Complete!              ║"
echo "╚═══════════════════════════════════════════════╝"
echo ""
echo "  🌐 Frontend  : $FRONTEND_URL"
echo "  ⚙️  Backend   : $BACKEND_URL"
echo "  📖 API Docs  : $BACKEND_URL/docs"
echo "  🏥 Health    : $BACKEND_URL/api/ping"
echo ""
echo "  Submit this URL → $FRONTEND_URL"
echo ""
