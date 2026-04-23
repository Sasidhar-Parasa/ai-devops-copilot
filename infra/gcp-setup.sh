#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
#  AI DevOps Copilot — GCP Prerequisites Setup
#
#  Run ONCE before using Terraform or GitHub Actions.
#  This script handles everything that must exist before tf apply.
#
#  Usage:
#    export GCP_PROJECT_ID="your-project-id"
#    export GCP_REGION="us-central1"        # optional, defaults to us-central1
#    bash infra/gcp-setup.sh
# ═══════════════════════════════════════════════════════════════════
set -euo pipefail

# ── Config ────────────────────────────────────────────────────────
PROJECT_ID="${GCP_PROJECT_ID:?❌ Set GCP_PROJECT_ID before running}"
REGION="${GCP_REGION:-us-central1}"
TF_STATE_BUCKET="${PROJECT_ID}-tf-state"

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║     AI DevOps Copilot — GCP Setup                   ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "  Project : $PROJECT_ID"
echo "  Region  : $REGION"
echo "  TF State: gs://$TF_STATE_BUCKET"
echo ""

# ── Step 1: Authenticate ──────────────────────────────────────────
echo "▶ [1/6] Authenticating with GCP..."
gcloud auth login --quiet
gcloud auth application-default login --quiet
gcloud config set project "$PROJECT_ID" --quiet
gcloud config set compute/region "$REGION" --quiet
echo "   ✅ Authenticated as $(gcloud auth list --filter=status:ACTIVE --format='value(account)' | head -1)"

# ── Step 2: Enable APIs ───────────────────────────────────────────
echo ""
echo "▶ [2/6] Enabling required GCP APIs (this takes ~2 minutes)..."

APIS=(
  "run.googleapis.com"
  "artifactregistry.googleapis.com"
  "cloudbuild.googleapis.com"
  "iam.googleapis.com"
  "iamcredentials.googleapis.com"
  "secretmanager.googleapis.com"
  "logging.googleapis.com"
  "monitoring.googleapis.com"
  "cloudresourcemanager.googleapis.com"
)

gcloud services enable "${APIS[@]}" --project="$PROJECT_ID" --quiet

echo "   ✅ APIs enabled:"
for api in "${APIS[@]}"; do
  echo "      - $api"
done

# ── Step 3: Create Terraform state bucket ─────────────────────────
echo ""
echo "▶ [3/6] Creating Terraform remote state bucket..."

if gsutil ls "gs://$TF_STATE_BUCKET" &>/dev/null; then
  echo "   ℹ️  Bucket gs://$TF_STATE_BUCKET already exists"
else
  gsutil mb -p "$PROJECT_ID" -l "$REGION" "gs://$TF_STATE_BUCKET"
  # Enable versioning to protect against accidental state deletion
  gsutil versioning set on "gs://$TF_STATE_BUCKET"
  # Enable uniform bucket-level access
  gsutil uniformbucketlevelaccess set on "gs://$TF_STATE_BUCKET"
  echo "   ✅ Created: gs://$TF_STATE_BUCKET (versioning enabled)"
fi

# ── Step 4: Update Terraform backend config ───────────────────────
echo ""
echo "▶ [4/6] Patching Terraform backend config with your bucket name..."

MAIN_TF="$(dirname "$0")/terraform/main.tf"
if [[ -f "$MAIN_TF" ]]; then
  sed -i "s/REPLACE_WITH_YOUR_PROJECT_ID-tf-state/${TF_STATE_BUCKET}/" "$MAIN_TF"
  echo "   ✅ Updated infra/terraform/main.tf backend bucket → gs://$TF_STATE_BUCKET"
else
  echo "   ⚠️  Could not find $MAIN_TF — update the bucket name manually"
fi

# ── Step 5: Create prod.tfvars ────────────────────────────────────
echo ""
echo "▶ [5/6] Creating prod.tfvars from template..."

TFVARS_EXAMPLE="$(dirname "$0")/terraform/prod.tfvars.example"
TFVARS_OUT="$(dirname "$0")/terraform/prod.tfvars"

if [[ -f "$TFVARS_OUT" ]]; then
  echo "   ℹ️  prod.tfvars already exists — skipping (edit manually if needed)"
else
  if [[ -f "$TFVARS_EXAMPLE" ]]; then
    cp "$TFVARS_EXAMPLE" "$TFVARS_OUT"
    sed -i "s/your-gcp-project-id/$PROJECT_ID/" "$TFVARS_OUT"
    sed -i "s/region     = \"us-central1\"/region     = \"$REGION\"/" "$TFVARS_OUT"
    echo "   ✅ Created infra/terraform/prod.tfvars"
    echo "   👉 Edit it to add your GROQ_API_KEY"
  fi
fi

# ── Step 6: Summary and next steps ───────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║          ✅ GCP Setup Complete!                      ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "  Next steps:"
echo ""
echo "  1. Add your Groq API key to infra/terraform/prod.tfvars:"
echo "     groq_api_key = \"gsk_...\""
echo ""
echo "  2. Run Terraform:"
echo "     cd infra/terraform"
echo "     terraform init"
echo "     terraform plan -var-file=prod.tfvars"
echo "     terraform apply -var-file=prod.tfvars"
echo ""
echo "  3. Get your GitHub secret key:"
echo "     terraform output -raw cicd_sa_key_json > /tmp/sa-key.json"
echo "     cat /tmp/sa-key.json   # copy this into GitHub Secrets as GCP_SA_KEY"
echo "     rm /tmp/sa-key.json"
echo ""
echo "  4. Add GitHub Secrets (Settings → Secrets → Actions):"
echo "     GCP_PROJECT_ID = $PROJECT_ID"
echo "     GCP_REGION     = $REGION"
echo "     GCP_SA_KEY     = <paste the JSON from step 3>"
echo ""
