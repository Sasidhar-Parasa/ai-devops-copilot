# 🚀 AI DevOps Copilot — CI/CD & Terraform Complete Guide

## Architecture Overview

```
GitHub Push (main)
       │
       ▼
┌─────────────────────────────────────────────────────────┐
│              GitHub Actions Pipeline                     │
│                                                         │
│  Job 1: test          Job 2: deploy-backend             │
│  ─────────────        ────────────────────              │
│  • Checkout           • Auth to GCP                     │
│  • Setup Python       • Build Docker image              │
│  • pip install        • Push to Artifact Registry       │
│  • ruff lint          • Deploy to Cloud Run             │
│  • pytest (16 tests)  • Smoke test /api/ping            │
│                                                         │
│                       Job 3: deploy-frontend            │
│                       ─────────────────────             │
│                       • Build with backend URL baked in │
│                       • Push to Artifact Registry       │
│                       • Deploy to Cloud Run             │
└─────────────────────────────────────────────────────────┘
       │
       ▼
GCP Artifact Registry
(us-central1-docker.pkg.dev/PROJECT/copilot/backend:sha-abc123)
       │
       ▼
Cloud Run (backend)  ←──── Cloud Run (frontend)
https://ai-copilot-backend-xxx.run.app
```

---

## Part 1: Prerequisites (Local Machine)

### 1.1 Install required tools (Ubuntu/WSL)

```bash
# ── gcloud CLI ────────────────────────────────────────────────────
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
gcloud init

# ── Terraform ─────────────────────────────────────────────────────
sudo apt-get update && sudo apt-get install -y gnupg software-properties-common
wget -O- https://apt.releases.hashicorp.com/gpg | \
  gpg --dearmor | sudo tee /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] \
  https://apt.releases.hashicorp.com $(lsb_release -cs) main" | \
  sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt-get update && sudo apt-get install -y terraform

# ── Verify ────────────────────────────────────────────────────────
gcloud version
terraform version
docker version
git --version
```

### 1.2 Get a FREE Groq API key (2 minutes)

```
1. Go to https://console.groq.com
2. Sign up (free, no credit card)
3. Navigate to API Keys → Create API Key
4. Copy the key (starts with gsk_...)
```

---

## Part 2: GCP Setup (Run Once)

### 2.1 Create a GCP Project

```bash
# If you don't have a project yet
gcloud projects create ai-devops-copilot-2024 \
  --name="AI DevOps Copilot"

# Link billing account (required for Cloud Run)
gcloud billing accounts list  # copy ACCOUNT_ID
gcloud billing projects link ai-devops-copilot-2024 \
  --billing-account=ACCOUNT_ID
```

### 2.2 Run the automated GCP setup script

```bash
cd ai-devops-copilot

export GCP_PROJECT_ID="ai-devops-copilot-2024"   # ← your project ID
export GCP_REGION="us-central1"

bash infra/gcp-setup.sh
```

This script:
- Enables all 9 required APIs
- Creates GCS bucket for Terraform state
- Updates `main.tf` backend config with your bucket name
- Creates `infra/terraform/prod.tfvars` from the example template

### 2.3 Add your Groq API key to prod.tfvars

```bash
# Edit the file created by the setup script
nano infra/terraform/prod.tfvars

# Set:
groq_api_key = "gsk_your_key_here"
```

---

## Part 3: Terraform — Provision GCP Infrastructure

### 3.1 Initialize Terraform

```bash
cd infra/terraform

# Download providers and configure remote backend
terraform init

# Expected output:
# ✅ Initializing the backend...
# ✅ Initializing provider plugins...
# ✅ Terraform has been successfully initialized!
```

### 3.2 Plan — preview what will be created

```bash
terraform plan -var-file=prod.tfvars

# Review the plan carefully. You should see:
# + google_artifact_registry_repository.main
# + google_cloud_run_v2_service.main (backend)
# + google_cloud_run_v2_service.main (frontend)
# + google_service_account.cicd
# + google_service_account.cloudrun
# + google_service_account_key.cicd
# + google_secret_manager_secret.groq_api_key
# ... and IAM bindings
```

### 3.3 Apply — create the infrastructure

```bash
terraform apply -var-file=prod.tfvars

# Type 'yes' when prompted
# Takes ~3-5 minutes

# Expected outputs:
# backend_url                   = "https://ai-copilot-backend-xxx.run.app"
# frontend_url                  = "https://ai-copilot-frontend-xxx.run.app"
# artifact_registry_url         = "us-central1-docker.pkg.dev/PROJECT/copilot"
# cicd_service_account_email    = "copilot-cicd@PROJECT.iam.gserviceaccount.com"
# cloudrun_service_account_email= "copilot-cloudrun@PROJECT.iam.gserviceaccount.com"
```

### 3.4 Extract the CI/CD service account key

```bash
# Get the JSON key (needed for GitHub Secrets)
terraform output -raw cicd_sa_key_json > /tmp/cicd-sa-key.json

# Verify it's valid
cat /tmp/cicd-sa-key.json | python3 -m json.tool | head -5

# Copy contents — you'll paste this into GitHub Secrets
cat /tmp/cicd-sa-key.json

# Clean up immediately after copying
rm /tmp/cicd-sa-key.json
```

---

## Part 4: GitHub Repository Setup

### 4.1 Push your code to GitHub

```bash
cd ai-devops-copilot

# Initialize git if not already done
git init
git add .
git commit -m "feat: AI DevOps Copilot with CI/CD and Terraform"

# Create repo on GitHub (using GitHub CLI)
gh repo create ai-devops-copilot --public --push --source=.

# Or manually:
# 1. Create repo at github.com/new
# 2. git remote add origin https://github.com/YOUR_USER/ai-devops-copilot.git
# 3. git push -u origin main
```

### 4.2 Configure GitHub Secrets

Go to: **GitHub repo → Settings → Secrets and variables → Actions → New repository secret**

Add these 3 secrets:

| Secret Name | Value | How to get |
|-------------|-------|------------|
| `GCP_PROJECT_ID` | `your-project-id` | Your GCP project ID |
| `GCP_REGION` | `us-central1` | Your chosen region |
| `GCP_SA_KEY` | `{ "type": "service_account", ... }` | Output from `terraform output -raw cicd_sa_key_json` |

**Via GitHub CLI (faster):**

```bash
gh secret set GCP_PROJECT_ID --body "your-project-id"
gh secret set GCP_REGION     --body "us-central1"
gh secret set GCP_SA_KEY     < /tmp/cicd-sa-key.json  # paste before deleting
```

### 4.3 Trigger your first deployment

```bash
# The workflow triggers automatically on push to main
# Make a small change and push:
echo "# CI/CD enabled $(date)" >> README.md
git add README.md
git commit -m "ci: trigger first CI/CD pipeline run"
git push origin main
```

Watch the pipeline:
```
GitHub repo → Actions tab → CI/CD Pipeline
```

---

## Part 5: Verify Deployment

### 5.1 Check GitHub Actions results

```
GitHub → Actions → CI/CD Pipeline → (latest run)

You should see:
  ✅ 🧪 Lint & Test        (16 tests passing)
  ✅ 🚀 Build & Deploy Backend
  ✅ 🎨 Build & Deploy Frontend

Click "Build & Deploy Backend" → Deployment summary:
  Frontend: https://ai-copilot-frontend-xxx.run.app
  Backend:  https://ai-copilot-backend-xxx.run.app
```

### 5.2 Smoke test from your terminal

```bash
# Get your backend URL from Terraform output or GitHub Actions summary
BACKEND_URL=$(cd infra/terraform && terraform output -raw backend_url)
FRONTEND_URL=$(cd infra/terraform && terraform output -raw frontend_url)

echo "Backend:  $BACKEND_URL"
echo "Frontend: $FRONTEND_URL"

# Health check
curl -s "$BACKEND_URL/api/ping" | python3 -m json.tool
# Expected: { "status": "ok", "llm": "groq", "gcp_project": "your-project" }

# Test chat endpoint
curl -s -X POST "$BACKEND_URL/api/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "system health check", "session_id": "smoke-test"}' \
  | python3 -m json.tool | head -20

# Open frontend
echo "Open in browser: $FRONTEND_URL"
```

### 5.3 View real-time Cloud Run logs

```bash
# Backend logs (tail last 50 lines)
gcloud logging read \
  'resource.type="cloud_run_revision" AND resource.labels.service_name="ai-copilot-backend"' \
  --limit=50 \
  --format="table(timestamp,severity,textPayload)" \
  --project="$GCP_PROJECT_ID"

# Or stream live
gcloud alpha logging tail \
  'resource.type="cloud_run_revision"' \
  --project="$GCP_PROJECT_ID"
```

---

## Part 6: Deployment Flow Explained

```
Developer pushes to main
        │
        ▼
[GitHub Actions: Job 1 — test]
1. Checkout code
2. pip install -r requirements.txt
3. ruff check . (lint, non-blocking)
4. pytest tests/ -v (16 tests — if any fail, pipeline STOPS here)
        │
        ▼ (only if tests pass AND push to main)
[GitHub Actions: Job 2 — deploy-backend]
5. google-github-actions/auth → authenticates using GCP_SA_KEY secret
6. docker/setup-buildx-action → enables layer caching
7. docker/build-push-action:
   - Reads ./backend/Dockerfile
   - Multi-stage build (builder → runtime)
   - Caches layers in GitHub Actions cache (faster subsequent builds)
   - Tags with git SHA: sha-abc1234
   - Tags with: latest
   - Pushes to: us-central1-docker.pkg.dev/PROJECT/copilot/backend:latest
8. google-github-actions/deploy-cloudrun:
   - Calls: gcloud run deploy ai-copilot-backend --image=...
   - Sets env vars and secrets
   - Returns service URL
9. Smoke test: curl /api/ping → must return 200 or pipeline fails
        │
        ▼ (uses backend URL from Job 2 output)
[GitHub Actions: Job 3 — deploy-frontend]
10. Build frontend Docker image with VITE_API_URL baked in
11. Push to Artifact Registry
12. Deploy to Cloud Run
        │
        ▼
LIVE: https://your-app.run.app ✅
```

---

## Part 7: Common Errors & Fixes

### ❌ Error: "Permission denied" / 403 on gcloud

```
ERROR: (gcloud.run.deploy) PERMISSION_DENIED: The caller does not have permission
```

**Fix:**
```bash
# Check which account you're using
gcloud auth list

# Re-authenticate
gcloud auth login
gcloud auth application-default login

# Verify SA has correct roles
gcloud projects get-iam-policy $GCP_PROJECT_ID \
  --flatten="bindings[].members" \
  --filter="bindings.members:copilot-cicd@" \
  --format="table(bindings.role)"
```

---

### ❌ Error: GitHub Actions "google-github-actions/auth failed"

```
Error: google-github-actions/auth failed with: failed to generate auth token
```

**Fix:**
```bash
# 1. Verify GCP_SA_KEY secret is valid JSON
# In GitHub: Settings → Secrets → GCP_SA_KEY → "Update secret"
# Paste the COMPLETE JSON including { and }

# 2. Test the key locally
echo '${{ secrets.GCP_SA_KEY }}' > /tmp/test-key.json
gcloud auth activate-service-account --key-file=/tmp/test-key.json
rm /tmp/test-key.json

# 3. Check the SA key hasn't expired (keys expire after 10 years by default)
# Regenerate via Terraform if needed:
cd infra/terraform
terraform destroy -target=module.iam.google_service_account_key.cicd -var-file=prod.tfvars
terraform apply -target=module.iam -var-file=prod.tfvars
terraform output -raw cicd_sa_key_json
# Re-add to GitHub Secrets
```

---

### ❌ Error: "Artifact Registry repository not found"

```
ERROR: failed to push image: repository not found
```

**Fix:**
```bash
# The repository must exist before pushing images
# Terraform creates it, but if you skipped Terraform:
gcloud artifacts repositories create copilot \
  --repository-format=docker \
  --location=us-central1 \
  --project=$GCP_PROJECT_ID

# Also configure Docker auth
gcloud auth configure-docker us-central1-docker.pkg.dev
```

---

### ❌ Error: "Dockerfile not found" in Cloud Build

```
error: failed to solve: failed to read dockerfile
```

**Fix:**
```bash
# Verify Dockerfile exists at backend/Dockerfile
ls -la backend/Dockerfile

# Check .dockerignore isn't excluding it (it shouldn't be)
cat backend/.dockerignore | grep Dockerfile

# Test the build locally first
cd backend
docker build -t test-build .
docker run -p 8080:8080 test-build
curl http://localhost:8080/api/ping
```

---

### ❌ Error: "Cloud Run service failed health check"

```
ERROR: Cloud Run error: Container failed to start.
Health check failed after 240s.
```

**Fix:**
```bash
# 1. Check Cloud Run logs
gcloud logging read \
  'resource.type=cloud_run_revision severity>=ERROR' \
  --limit=20 --project=$GCP_PROJECT_ID

# 2. Common causes:
#    a) App crashes on startup → check for missing env vars
#    b) Wrong PORT → Cloud Run injects PORT env var, app must use it
#    c) App binds to 127.0.0.1 instead of 0.0.0.0

# 3. Test locally with same env
docker run -e PORT=8080 -p 8080:8080 \
  us-central1-docker.pkg.dev/$GCP_PROJECT_ID/copilot/backend:latest

# 4. Verify the health check path returns 200
curl http://localhost:8080/api/ping
```

---

### ❌ Error: Terraform "Error: Backend configuration changed"

```
Error: Backend initialization required, please run "terraform init"
```

**Fix:**
```bash
cd infra/terraform
terraform init -reconfigure
```

---

### ❌ Error: "quota exceeded" on Cloud Run

```
ERROR: Quota exceeded for quota metric 'run.googleapis.com/requests'
```

**Fix:**
```bash
# Request quota increase in GCP Console:
# IAM & Admin → Quotas → search "Cloud Run"
# Or reduce max-instances in terraform:
# backend_max_instances = 2
```

---

### ❌ Error: pytest import errors in GitHub Actions

```
ModuleNotFoundError: No module named 'fastapi'
```

**Fix:**
```bash
# Ensure the working-directory is set correctly in the workflow:
# working-directory: backend

# And requirements include test deps:
echo "pytest==7.4.0
pytest-asyncio==0.21.0
httpx==0.27.0" >> backend/requirements.txt
git add backend/requirements.txt
git commit -m "fix: add test dependencies to requirements.txt"
```

---

## Part 8: Cost Optimization

Cloud Run with scale-to-zero is essentially **free** for low-traffic demo apps:

| Resource | Free tier | Typical monthly cost |
|----------|-----------|---------------------|
| Cloud Run requests | 2M req/month free | ~$0 for demos |
| Cloud Run CPU | 360,000 vCPU-seconds/month free | ~$0 for demos |
| Artifact Registry | 0.5 GB free | ~$0 (our images ~180MB each) |
| Cloud Build | 120 min/day free | ~$0 for 10 builds/day |
| Secret Manager | 6 active secret versions free | $0 |
| GCS (TF state) | 5GB free | ~$0 |

**Estimated total: $0–$2/month** for a demo/hackathon project.

---

## Part 9: Useful Commands Reference

```bash
# ── Terraform ──────────────────────────────────────────────────────
terraform init                              # Initialize
terraform plan -var-file=prod.tfvars       # Preview changes
terraform apply -var-file=prod.tfvars      # Apply changes
terraform destroy -var-file=prod.tfvars    # Tear down everything
terraform output                           # Show all outputs
terraform output -raw backend_url          # Get specific output

# ── Cloud Run ──────────────────────────────────────────────────────
gcloud run services list                   # List all services
gcloud run services describe SERVICE_NAME  # Service details
gcloud run revisions list                  # List all revisions
gcloud run services update-traffic SERVICE_NAME --to-latest  # Route to latest

# ── Logs ───────────────────────────────────────────────────────────
gcloud logging read 'resource.type=cloud_run_revision' --limit=50
gcloud alpha logging tail 'resource.type=cloud_run_revision'

# ── Artifact Registry ──────────────────────────────────────────────
gcloud artifacts repositories list
gcloud artifacts docker images list us-central1-docker.pkg.dev/PROJECT/copilot

# ── Rollback ───────────────────────────────────────────────────────
# Route traffic to a previous revision
gcloud run services update-traffic ai-copilot-backend \
  --to-revisions=ai-copilot-backend-00002-abc=100

# ── Force redeploy ─────────────────────────────────────────────────
git commit --allow-empty -m "ci: force redeploy"
git push origin main
```
