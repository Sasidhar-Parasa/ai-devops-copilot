#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:?❌ Export GCP_PROJECT_ID first}"

echo "Finding Cloud Run SA..."
SA_EMAIL=$(gcloud run services describe ai-copilot-backend \
  --region=us-central1 \
  --format="value(spec.template.spec.serviceAccountName)" \
  --project="$PROJECT_ID" 2>/dev/null || echo "")

[ -z "$SA_EMAIL" ] && SA_EMAIL="copilot-cloudrun@${PROJECT_ID}.iam.gserviceaccount.com"
echo "SA: $SA_EMAIL | Project: $PROJECT_ID"
echo ""

ROLES=(
  "roles/cloudbuild.builds.editor"
  "roles/run.admin"
  "roles/artifactregistry.writer"
  "roles/iam.serviceAccountUser"
  "roles/storage.admin"
  "roles/logging.viewer"          # needed to poll build status + read logs
  "roles/logging.logWriter"
)

for role in "${ROLES[@]}"; do
  echo "  + $role"
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="$role" --quiet 2>/dev/null
done

echo ""
echo "✅ Done! Push to redeploy:"
echo "   git add backend/services/deploy_service.py"
echo "   git commit -m 'fix: async build submit + polling'"
echo "   git push origin main"