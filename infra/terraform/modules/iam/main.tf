# ═══════════════════════════════════════════════════════════════════
#  Module: IAM
#  Creates two service accounts with least-privilege roles:
#
#  1. cicd-sa  — used by GitHub Actions to build + deploy
#  2. cloudrun-sa — used by Cloud Run services at runtime
# ═══════════════════════════════════════════════════════════════════

# ── Service Account 1: CI/CD (GitHub Actions) ─────────────────────────────────
resource "google_service_account" "cicd" {
  account_id   = "copilot-cicd"
  display_name = "AI Copilot CI/CD (GitHub Actions)"
  description  = "Used by GitHub Actions to build images and deploy to Cloud Run"
  project      = var.project_id
}

# Roles needed by GitHub Actions to deploy
locals {
  cicd_roles = [
    "roles/run.admin",                      # Deploy/manage Cloud Run services
    "roles/artifactregistry.writer",         # Push Docker images
    "roles/iam.serviceAccountUser",          # Impersonate cloudrun-sa during deploy
    "roles/cloudbuild.builds.editor",        # Trigger Cloud Build
    "roles/secretmanager.secretAccessor",    # Read secrets during deploy (optional)
    "roles/logging.viewer",                  # View logs for smoke tests
  ]
}

resource "google_project_iam_member" "cicd_roles" {
  for_each = toset(local.cicd_roles)

  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.cicd.email}"
}

# Allow CI/CD SA to deploy AS the cloudrun SA (required by gcloud run deploy)
resource "google_service_account_iam_member" "cicd_acts_as_cloudrun" {
  service_account_id = google_service_account.cloudrun.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.cicd.email}"
}

# Generate JSON key for the CI/CD service account
# This is what you add to GitHub Secrets as GCP_SA_KEY
resource "google_service_account_key" "cicd" {
  service_account_id = google_service_account.cicd.name
  public_key_type    = "TYPE_X509_PEM_FILE"
  private_key_type   = "TYPE_GOOGLE_CREDENTIALS_FILE"

  lifecycle {
    # Rotate key by destroying and recreating
    create_before_destroy = true
  }
}

# ── Service Account 2: Cloud Run Runtime ──────────────────────────────────────
resource "google_service_account" "cloudrun" {
  account_id   = "copilot-cloudrun"
  display_name = "AI Copilot Cloud Run Runtime"
  description  = "Minimal runtime identity for Cloud Run services"
  project      = var.project_id
}

locals {
  cloudrun_roles = [
    "roles/logging.logWriter",              # Write structured logs to Cloud Logging
    "roles/monitoring.metricWriter",        # Write custom metrics
    "roles/cloudtrace.agent",               # Distributed tracing
    "roles/secretmanager.secretAccessor",   # Read secrets (Groq/Gemini keys)
    "roles/run.viewer",                     # List Cloud Run services (for monitoring)
    "roles/artifactregistry.reader",        # Pull own images
  ]
}

resource "google_project_iam_member" "cloudrun_roles" {
  for_each = toset(local.cloudrun_roles)

  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.cloudrun.email}"
}

# Grant cloudrun-sa access to pull images from Artifact Registry
resource "google_artifact_registry_repository_iam_member" "cloudrun_reader" {
  project    = var.project_id
  location   = var.region
  repository = var.repo_name
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${google_service_account.cloudrun.email}"
}
