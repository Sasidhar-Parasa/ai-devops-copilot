# 🤖 AI DevOps Copilot
### Multi-Agent Deployment & Incident Management System

A production-ready AI-powered DevOps assistant with a **multi-agent architecture** that lets you deploy apps, monitor health, detect failures, perform root cause analysis, and trigger automated fixes — all via natural language.

---

## 🏗️ Architecture

```
User Input (Natural Language)
        │
        ▼
┌─────────────────────────────────┐
│     Coordinator Agent (AI)      │  ← Intent detection + task routing
└─────────────┬───────────────────┘
              │
    ┌─────────┼─────────┐──────────┐──────────┐
    ▼         ▼         ▼          ▼          ▼
Deployment  Monitor  Incident  Root Cause   Fix
  Agent      Agent    Agent      Agent      Agent
    │         │         │          │          │
  CI/CD    Logs &    Anomaly    Failure    Auto-
Simulation Metrics  Detection  Analysis Remediation
```

---

## 📁 Project Structure

```
ai-devops-copilot/
├── backend/
│   ├── main.py                # FastAPI app entrypoint
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .env.example
│   ├── agents/
│   │   ├── coordinator.py     # Primary orchestrator
│   │   ├── deployment_agent.py
│   │   ├── monitoring_agent.py
│   │   ├── incident_agent.py
│   │   ├── root_cause_agent.py
│   │   └── fix_agent.py
│   ├── models/
│   │   └── schemas.py         # Pydantic models
│   ├── routers/
│   │   ├── chat.py            # POST /api/chat
│   │   ├── deployments.py     # POST /api/deploy, /rollback
│   │   ├── logs.py            # GET /api/logs
│   │   └── health.py          # GET /api/health, /incidents
│   └── services/
│       ├── ai_service.py      # OpenAI/Ollama/fallback
│       └── database.py        # SQLite CRUD + seeding
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── pages/
│   │   │   ├── ChatPage.jsx
│   │   │   └── DashboardPage.jsx
│   │   ├── components/
│   │   │   ├── chat/
│   │   │   │   ├── ChatMessage.jsx   # Markdown + agent trace
│   │   │   │   └── ChatInput.jsx     # Quick commands + textarea
│   │   │   ├── dashboard/
│   │   │   │   ├── PipelineCard.jsx  # Build→Test→Deploy viz
│   │   │   │   ├── ServiceHealthGrid.jsx
│   │   │   │   ├── LogsPanel.jsx
│   │   │   │   ├── IncidentsSection.jsx
│   │   │   │   └── StatsRow.jsx
│   │   │   └── shared/
│   │   │       └── Sidebar.jsx
│   │   ├── hooks/
│   │   │   ├── useChat.js
│   │   │   └── useDashboard.js
│   │   └── utils/api.js
│   └── Dockerfile
│
├── infra/
│   └── deploy.sh              # One-click GCP deployment
├── docker-compose.yml
└── README.md
```

---

## 🚀 Quick Start (Local)

### Prerequisites
- Python 3.11+
- Node.js 18+
- (Optional) OpenAI API key for best AI responses

### 1. Clone & setup backend

```bash
cd ai-devops-copilot/backend

# Create virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY (optional)

# Start backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Backend will be live at: http://localhost:8000
API docs at: http://localhost:8000/docs

### 2. Setup frontend

```bash
cd ai-devops-copilot/frontend

# Install dependencies
npm install

# Configure environment
cp .env.example .env
# VITE_API_URL=http://localhost:8000/api  (default, no change needed)

# Start dev server
npm run dev
```

Frontend will be live at: http://localhost:5173

### 3. Docker Compose (both at once)

```bash
cd ai-devops-copilot
OPENAI_API_KEY=sk-... docker compose up --build

# Frontend: http://localhost:3000
# Backend:  http://localhost:8000
```

---

## 🧪 Testing

### Sample API requests

```bash
# Health check
curl http://localhost:8000/api/ping

# System health
curl http://localhost:8000/api/health | jq .

# Fetch logs
curl "http://localhost:8000/api/logs?limit=10" | jq .

# List deployments
curl http://localhost:8000/api/deployments | jq .

# List incidents
curl http://localhost:8000/api/incidents | jq .
```

### Chat endpoint (main AI interface)

```bash
# Deploy an app
curl -s -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "deploy myapp v2.5.0", "session_id": "demo"}' | jq '{intent, agents: [.agents_used[].agent]}'

# Root cause analysis
curl -s -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "why did the deployment fail?", "session_id": "demo"}' | jq .response

# Auto-fix
curl -s -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "auto fix the payment service", "session_id": "demo"}' | jq .

# Rollback
curl -s -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "rollback payment-service", "session_id": "demo"}' | jq .

# System status
curl -s -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "show system health", "session_id": "demo"}' | jq .
```

### Direct deploy/rollback endpoints

```bash
# Trigger deployment
curl -s -X POST http://localhost:8000/api/deploy \
  -H "Content-Type: application/json" \
  -d '{"app_name": "myapp", "version": "v3.0.0", "environment": "production"}' | jq .

# Rollback
curl -s -X POST http://localhost:8000/api/rollback \
  -H "Content-Type: application/json" \
  -d '{"app_name": "payment-service", "reason": "Error rate too high"}' | jq .
```

### Sample chat commands to try in the UI

| Command | Agent Chain |
|---------|-------------|
| `deploy myapp v2.5.0` | Coordinator → Deployment |
| `rollback payment-service` | Coordinator → Deployment |
| `why did the deployment fail?` | Coordinator → Monitoring → RCA |
| `show me recent errors` | Coordinator → Monitoring |
| `any active incidents?` | Coordinator → Incident |
| `auto fix the payment service` | Coordinator → Incident → Fix |
| `system health check` | Coordinator → Monitoring |

---

## ☁️ GCP Deployment (Step-by-Step)

### Prerequisites
1. Google Cloud account with $300 free credits
2. `gcloud` CLI installed: https://cloud.google.com/sdk/docs/install
3. A GCP project created

### Step-by-step commands

```bash
# 1. Login to GCP
gcloud auth login

# 2. Set your project
export PROJECT_ID="your-project-id"    # ← CHANGE THIS
export REGION="us-central1"
gcloud config set project $PROJECT_ID

# 3. Enable required APIs
gcloud services enable \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com

# 4. Create Artifact Registry repository
gcloud artifacts repositories create copilot \
    --repository-format=docker \
    --location=$REGION \
    --description="AI DevOps Copilot"

# 5. Authenticate Docker with GCP
gcloud auth configure-docker $REGION-docker.pkg.dev

# ── Deploy Backend ──────────────────────────────────────────────────

# 6. Build and push backend image
cd backend
gcloud builds submit \
    --tag "$REGION-docker.pkg.dev/$PROJECT_ID/copilot/backend:latest" \
    --timeout=10m

# 7. Deploy backend to Cloud Run
gcloud run deploy ai-copilot-backend \
    --image "$REGION-docker.pkg.dev/$PROJECT_ID/copilot/backend:latest" \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --memory 512Mi \
    --cpu 1 \
    --set-env-vars "OPENAI_API_KEY=sk-...,LOG_LEVEL=INFO"

# 8. Get backend URL
BACKEND_URL=$(gcloud run services describe ai-copilot-backend \
    --region $REGION --format="value(status.url)")
echo "Backend: $BACKEND_URL"

# ── Deploy Frontend ─────────────────────────────────────────────────

# 9. Build and push frontend image (injects backend URL at build time)
cd ../frontend
gcloud builds submit \
    --tag "$REGION-docker.pkg.dev/$PROJECT_ID/copilot/frontend:latest" \
    --timeout=10m \
    --build-arg "VITE_API_URL=${BACKEND_URL}/api"

# 10. Deploy frontend to Cloud Run
gcloud run deploy ai-copilot-frontend \
    --image "$REGION-docker.pkg.dev/$PROJECT_ID/copilot/frontend:latest" \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --memory 256Mi \
    --cpu 1

# 11. Get frontend URL (this is your public URL!)
gcloud run services describe ai-copilot-frontend \
    --region $REGION --format="value(status.url)"
```

### One-click deployment

```bash
export GCP_PROJECT_ID="your-project-id"
export OPENAI_API_KEY="sk-..."      # optional
bash infra/deploy.sh
```

---

## 🤖 AI Configuration

The system tries providers in this order:

1. **OpenAI** (best quality) — set `OPENAI_API_KEY` in `.env`
2. **Ollama** (local, free) — install Ollama, run `ollama pull llama3`
3. **Rule-based fallback** — works with zero config, always available

### Using Ollama (free, local)

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model
ollama pull llama3

# Start Ollama (runs on port 11434)
ollama serve

# Set in .env
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3
```

---

## 🎯 Hackathon Demo Script

1. Open the app at your public URL
2. **Chat tab** — type: `deploy myapp v2.5.0`
   - Watch the multi-agent trace unfold
   - See Build → Test → Deploy pipeline
3. **Dashboard tab** — show live service health
   - Point out degraded payment-service (pre-seeded)
   - Show active incident card
4. Back to **Chat** — type: `why did the deployment fail?`
   - RCA agent fires with evidence & confidence score
5. Type: `auto fix the payment service`
   - Fix agent applies remediation, marks incident resolved
6. **Refresh dashboard** — incident is now resolved ✅

---

## 📊 API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Service info |
| `/api/ping` | GET | Health ping |
| `/api/chat` | POST | Main AI chat interface |
| `/api/deploy` | POST | Trigger deployment |
| `/api/rollback` | POST | Rollback app |
| `/api/deployments` | GET | List deployments |
| `/api/logs` | GET | Fetch system logs |
| `/api/health` | GET | System health metrics |
| `/api/incidents` | GET | List incidents |
| `/docs` | GET | Swagger UI |

---

## 💡 Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI, Python 3.11, Pydantic v2 |
| AI | OpenAI GPT-4o-mini / Ollama / Rule-based |
| Database | SQLite (via aiosqlite) |
| Frontend | React 18, Vite, Tailwind CSS |
| Icons | Lucide React |
| Deployment | Docker, GCP Cloud Run, Artifact Registry |
| CI/CD | Cloud Build |
# CI/CD enabled Thu Apr 23 17:24:27 UTC 2026
