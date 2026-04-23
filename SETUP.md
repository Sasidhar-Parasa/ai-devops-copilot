# 🚀 AI DevOps Copilot — Complete Setup Guide

## Step 1: Get FREE LLM API Key

### Option A: Groq (RECOMMENDED — Fast, Free, llama3-70b)
1. Go to https://console.groq.com
2. Sign up (free, no credit card)
3. Create API Key → copy it
4. Add to `.env`: `GROQ_API_KEY=gsk_...`

### Option B: Google Gemini (Free tier)
1. Go to https://aistudio.google.com
2. Click "Get API Key"
3. Add to `.env`: `GEMINI_API_KEY=AIza...`

> If neither is set, the system uses a smart **rule-based fallback** that
> still handles all intents correctly — just without free-form NLU.

---

## Step 2: Configure GCP (for real deployments)

```bash
# Install gcloud CLI
# https://cloud.google.com/sdk/docs/install

# Login
gcloud auth login
gcloud auth application-default login

# Set project
export PROJECT_ID="your-project-id"
gcloud config set project $PROJECT_ID

# Enable APIs
gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com

# Create Artifact Registry repo
gcloud artifacts repositories create copilot \
  --repository-format=docker \
  --location=us-central1

# Authenticate Docker
gcloud auth configure-docker us-central1-docker.pkg.dev
```

---

## Step 3: Create .env file

```bash
cd ai-devops-copilot/backend
cp .env.example .env
```

Edit `.env`:
```env
# LLM (at least one required for best experience)
GROQ_API_KEY=gsk_your_groq_key_here

# GCP (required for real deployments)
GCP_PROJECT_ID=your-project-id
GCP_REGION=us-central1
```

---

## Step 4: Run locally

```bash
# Terminal 1 — Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — Frontend
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

---

## Step 5: Deploy to GCP

```bash
export GCP_PROJECT_ID="your-project-id"
export GROQ_API_KEY="gsk_..."
bash infra/deploy.sh
```

---

## 🎯 Demo Conversation Flow

```
You:  deploy myapp
AI:   🚀 I can deploy your application! Please share your GitHub repo URL.

You:  https://github.com/tiangolo/fastapi
AI:   Cloning → Validating → Building → Deploying...
      ✅ Live at https://myapp-abc123-uc.a.run.app

You:  why did the deploy fail?
AI:   🔍 Root cause: Dockerfile missing PORT exposure...

You:  rollback payment-service
AI:   ⏪ Rolling back to v2.3.8...

You:  system health check
AI:   📊 5 services healthy, 1 degraded...
```

---

## 🔑 Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | Recommended | Free Groq API key (llama3-70b) |
| `GEMINI_API_KEY` | Optional | Google Gemini free tier key |
| `GCP_PROJECT_ID` | For real deploys | Your GCP project ID |
| `GCP_REGION` | Optional | Default: `us-central1` |
| `WORKSPACE_DIR` | Optional | Default: `/tmp/copilot-workspace` |
