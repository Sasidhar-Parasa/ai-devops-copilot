# 🚀 GCP Deployment Guide – AI DevOps Copilot

Complete step-by-step deployment using your $300 free credits.
Estimated cost: **~$0–5/month** on Cloud Run free tier.

---

## 📋 Prerequisites

- Google Cloud account with $300 free credits activated
- `gcloud` CLI installed → https://cloud.google.com/sdk/docs/install
- `docker` installed (for local testing only)
- `node` 18+ and `python` 3.11+

---

## STEP 1 — GCP Project Setup

```bash
# Login to GCP
gcloud auth login

# Create a new project (or use existing)
gcloud projects create ai-devops-copilot-demo --name="AI DevOps Copilot"

# Set as active project
gcloud config set project ai-devops-copilot-demo

# Enable required APIs
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  firebase.googleapis.com

# Confirm billing is enabled (required for Cloud Run)
gcloud beta billing accounts list
# Then link: gcloud beta billing projects link ai-devops-copilot-demo \
#   --billing-account=YOUR_BILLING_ACCOUNT_ID
```

---

## STEP 2 — Create Artifact Registry

```bash
# Set region (us-central1 is cheapest)
export REGION=us-central1
export PROJECT_ID=ai-devops-copilot-demo
export REPO=devops-copilot

# Create Docker repo in Artifact Registry
gcloud artifacts repositories create $REPO \
  --repository-format=docker \
  --location=$REGION \
  --description="AI DevOps Copilot images"

# Configure Docker auth
gcloud auth configure-docker $REGION-docker.pkg.dev
```

---

## STEP 3 — Deploy Backend to Cloud Run

```bash
cd ai-devops-copilot/backend

# Build and push image via Cloud Build (no local Docker needed!)
gcloud builds submit \
  --tag $REGION-docker.pkg.dev/$PROJECT_ID/$REPO/backend:latest \
  --timeout=10m

# Deploy to Cloud Run
gcloud run deploy ai-devops-backend \
  --image $REGION-docker.pkg.dev/$PROJECT_ID/$REPO/backend:latest \
  --region $REGION \
  --platform managed \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 5 \
  --port 8080 \
  --set-env-vars "APP_ENV=production,LOG_LEVEL=INFO,CORS_ORIGINS=*" \
  --set-env-vars "OPENAI_API_KEY=your-openai-key-here"

# ✅ Note the URL output — looks like:
# https://ai-devops-backend-xxxxxxxx-uc.a.run.app
export BACKEND_URL=$(gcloud run services describe ai-devops-backend \
  --region $REGION --format 'value(status.url)')
echo "Backend URL: $BACKEND_URL"
```

> **No OpenAI key?** The app works fine with rule-based agents. Just omit the OPENAI_API_KEY flag.

---

## STEP 4 — Deploy Frontend

### Option A: Firebase Hosting (Recommended — free, CDN, custom domain)

```bash
# Install Firebase CLI
npm install -g firebase-tools

# Login
firebase login

# Initialize in frontend dir
cd ai-devops-copilot/frontend

# Create .env with real backend URL
echo "VITE_API_URL=$BACKEND_URL/api" > .env

# Build with real API URL
npm run build

# Initialize Firebase (select "Hosting", use existing project)
firebase init hosting
# → Public directory: dist
# → Single-page app: Yes
# → Don't overwrite index.html

# Deploy
firebase deploy --only hosting

# ✅ Output: https://ai-devops-copilot-demo.web.app
```

### Option B: Cloud Run (if you prefer single platform)

```bash
cd ai-devops-copilot/frontend

# Build with backend URL baked in
echo "VITE_API_URL=$BACKEND_URL/api" > .env
npm run build

# Submit frontend build
gcloud builds submit \
  --tag $REGION-docker.pkg.dev/$PROJECT_ID/$REPO/frontend:latest \
  --timeout=10m

# Deploy frontend to Cloud Run
gcloud run deploy ai-devops-frontend \
  --image $REGION-docker.pkg.dev/$PROJECT_ID/$REPO/frontend:latest \
  --region $REGION \
  --platform managed \
  --allow-unauthenticated \
  --memory 256Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 3 \
  --port 8080

export FRONTEND_URL=$(gcloud run services describe ai-devops-frontend \
  --region $REGION --format 'value(status.url)')
echo "Frontend URL: $FRONTEND_URL"
```

---

## STEP 5 — Update CORS (point backend to frontend)

```bash
gcloud run services update ai-devops-backend \
  --region $REGION \
  --update-env-vars "FRONTEND_URL=$FRONTEND_URL,CORS_ORIGINS=$FRONTEND_URL"
```

---

## STEP 6 — Verify Everything Works

```bash
# Test backend health
curl $BACKEND_URL/api/ping
# Expected: {"status":"ok","service":"ai-devops-copilot"}

# Test chat endpoint
curl -X POST $BACKEND_URL/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "deploy myapp v2.0", "session_id": "test"}' | python3 -m json.tool

# Test logs
curl $BACKEND_URL/api/logs?limit=5 | python3 -m json.tool

# Test health dashboard
curl $BACKEND_URL/api/health | python3 -m json.tool
```

---

## 🧪 Local Development

### Run Backend

```bash
cd ai-devops-copilot/backend

# Create .env
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY (optional)

# Install dependencies
pip install -r requirements.txt

# Start server
uvicorn main:app --reload --port 8000

# API docs available at:
# http://localhost:8000/docs
```

### Run Frontend

```bash
cd ai-devops-copilot/frontend

# Install
npm install

# Create local env
echo "VITE_API_URL=http://localhost:8000/api" > .env

# Start dev server
npm run dev

# Open: http://localhost:5173
```

---

## 📝 Sample Chat Inputs to Demo

| Command | Agent Triggered |
|---------|----------------|
| `deploy myapp v2.5.0` | Coordinator → Deployment Agent |
| `rollback payment-service` | Coordinator → Deployment Agent (rollback) |
| `why did the last deployment fail?` | Coordinator → Monitoring → RCA Agent |
| `show me active incidents` | Coordinator → Incident Agent |
| `auto fix the payment service` | Coordinator → Incident → Fix Agent |
| `system health check` | Coordinator → Monitoring Agent |
| `show me recent errors` | Coordinator → Monitoring Agent |

---

## 💰 Estimated GCP Cost

| Service | Free Tier | Estimated Usage |
|---------|-----------|-----------------|
| Cloud Run Backend | 2M requests/mo free | ~$0 |
| Cloud Run Frontend | 2M requests/mo free | ~$0 |
| Artifact Registry | 0.5 GB free | ~$0 |
| Cloud Build | 120 min/day free | ~$0 |
| Firebase Hosting | 10 GB/mo free | ~$0 |
| **Total** | | **~$0–2/month** |

---

## 🔗 Final URLs

After deployment you'll have:
- **Frontend**: `https://ai-devops-copilot-demo.web.app` (Firebase) or Cloud Run URL
- **Backend API**: `https://ai-devops-backend-xxxx-uc.a.run.app`
- **API Docs**: `https://ai-devops-backend-xxxx-uc.a.run.app/docs`

Submit the frontend URL for judging! 🏆
