#!/usr/bin/env bash

PROJECT_ID="ai-devops-copilot-2024"
BUCKET="${PROJECT_ID}-tf-state"
USER_EMAIL=$(gcloud auth list --filter=status:ACTIVE --format='value(account)' | head -1)

echo "Fixing GCS access for: $USER_EMAIL"
echo "Bucket: gs://$BUCKET"
echo ""

echo "▶ Granting Storage Admin access..."
gsutil iam ch "user:${USER_EMAIL}:roles/storage.admin" "gs://${BUCKET}"

echo "▶ Refreshing application default credentials..."
gcloud auth application-default login

echo "▶ Setting project..."
gcloud config set project "$PROJECT_ID"

echo ""
echo "✅ Done! Now run:"
echo "cd infra/terraform && terraform init"
