#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
#  Workload Identity Federation Setup (Optional — Keyless Auth)
#
#  WIF is MORE SECURE than SA keys because:
#  - No long-lived credentials stored in GitHub Secrets
#  - GitHub OIDC token is exchanged for short-lived GCP tokens
#  - Tokens expire after 1 hour automatically
#
#  Run this INSTEAD OF using a SA JSON key in GitHub Secrets.
#  After running, update deploy.yml to use WIF (see below).
#
#  Usage:
#    export GCP_PROJECT_ID="your-project-id"
#    export GITHUB_REPO="your-username/ai-devops-copilot"
#    bash infra/setup-wif.sh
# ═══════════════════════════════════════════════════════════════════
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
GITHUB_REPO="${GITHUB_REPO:?Set GITHUB_REPO (format: owner/repo)}"
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
POOL_ID="github-actions-pool"
PROVIDER_ID="github-actions-provider"
SA_EMAIL="copilot-cicd@${PROJECT_ID}.iam.gserviceaccount.com"

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║   Workload Identity Federation Setup                 ║"
echo "╚══════════════════════════════════════════════════════╝"
echo "  Project    : $PROJECT_ID ($PROJECT_NUMBER)"
echo "  GitHub Repo: $GITHUB_REPO"
echo ""

# ── Step 1: Enable IAM Credentials API ───────────────────────────
echo "▶ [1/5] Enabling iamcredentials API..."
gcloud services enable iamcredentials.googleapis.com \
  --project="$PROJECT_ID" --quiet

# ── Step 2: Create Workload Identity Pool ─────────────────────────
echo "▶ [2/5] Creating Workload Identity Pool..."
gcloud iam workload-identity-pools create "$POOL_ID" \
  --project="$PROJECT_ID" \
  --location="global" \
  --display-name="GitHub Actions Pool" \
  --description="Pool for GitHub Actions CI/CD" \
  --quiet 2>/dev/null || echo "  Pool already exists"

# Get the pool full name
POOL_NAME="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}"

# ── Step 3: Create OIDC Provider ─────────────────────────────────
echo "▶ [3/5] Creating GitHub OIDC Provider..."
gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_ID" \
  --project="$PROJECT_ID" \
  --location="global" \
  --workload-identity-pool="$POOL_ID" \
  --display-name="GitHub Actions Provider" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
  --attribute-condition="assertion.repository=='${GITHUB_REPO}'" \
  --quiet 2>/dev/null || echo "  Provider already exists"

# ── Step 4: Bind SA to WIF Pool ──────────────────────────────────
echo "▶ [4/5] Binding service account to Workload Identity Pool..."
gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
  --project="$PROJECT_ID" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/${POOL_NAME}/attribute.repository/${GITHUB_REPO}" \
  --quiet

# ── Step 5: Output GitHub Secrets values ──────────────────────────
PROVIDER_FULL="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/providers/${PROVIDER_ID}"

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║      ✅ WIF Setup Complete!                          ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "  Add these to GitHub Secrets (instead of GCP_SA_KEY):"
echo ""
echo "  WIF_PROVIDER     = $PROVIDER_FULL"
echo "  WIF_SA_EMAIL     = $SA_EMAIL"
echo ""
echo "  Then in deploy.yml, replace the 'auth' step with:"
echo ""
echo "  - name: Authenticate to GCP (Keyless WIF)"
echo "    uses: google-github-actions/auth@v2"
echo "    with:"
echo "      workload_identity_provider: \${{ secrets.WIF_PROVIDER }}"
echo "      service_account: \${{ secrets.WIF_SA_EMAIL }}"
echo ""
echo "  Remove GCP_SA_KEY — it's no longer needed!"
echo ""
