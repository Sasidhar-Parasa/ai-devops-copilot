# ═══════════════════════════════════════════════════════════════════
#  AI DevOps Copilot — Terraform Root Configuration
#  Provisions: Artifact Registry + IAM + Cloud Run (backend + frontend)
# ═══════════════════════════════════════════════════════════════════

terraform {
  required_version = ">= 1.6"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.0"
    }
  }

  # Remote state in GCS — prevents state loss and enables team use
  # Run: gsutil mb gs://<your-project>-tf-state first
  backend "gcs" {
    bucket = "ai-devops-copilot-2024-tf-state"
    prefix = "ai-devops-copilot/prod"
  }
}

# ── Provider ─────────────────────────────────────────────────────────────────
provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}

# ── Enable required APIs ──────────────────────────────────────────────────────
resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "iam.googleapis.com",
    "secretmanager.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
  ])

  project            = var.project_id
  service            = each.key
  disable_on_destroy = false
}

# ── Artifact Registry ─────────────────────────────────────────────────────────
module "artifact_registry" {
  source = "./modules/artifact-registry"

  project_id  = var.project_id
  region      = var.region
  repo_name   = var.artifact_repo_name
  description = "AI DevOps Copilot Docker images"

  depends_on = [google_project_service.apis]
}

# ── IAM — Service Accounts ────────────────────────────────────────────────────
module "iam" {
  source = "./modules/iam"

  project_id   = var.project_id
  region       = var.region
  repo_name    = var.artifact_repo_name
  repo_location = var.region

  depends_on = [module.artifact_registry]
}

# ── Secrets (Groq API key stored in Secret Manager) ──────────────────────────
resource "google_secret_manager_secret" "groq_api_key" {
  secret_id = "groq-api-key"
  project   = var.project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "groq_api_key" {
  secret      = google_secret_manager_secret.groq_api_key.id
  secret_data = var.groq_api_key

  lifecycle {
    # Prevent terraform from showing the secret in diffs
    ignore_changes = [secret_data]
  }
}

resource "google_secret_manager_secret" "gemini_api_key" {
  secret_id = "gemini-api-key"
  project   = var.project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "gemini_api_key" {
  secret      = google_secret_manager_secret.gemini_api_key.id
  secret_data = var.gemini_api_key

  lifecycle {
    ignore_changes = [secret_data]
  }
}

# Grant Cloud Run SA access to secrets
resource "google_secret_manager_secret_iam_member" "cloudrun_groq" {
  secret_id = google_secret_manager_secret.groq_api_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${module.iam.cloudrun_sa_email}"
}

resource "google_secret_manager_secret_iam_member" "cloudrun_gemini" {
  secret_id = google_secret_manager_secret.gemini_api_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${module.iam.cloudrun_sa_email}"
}

# ── Cloud Run — Backend ───────────────────────────────────────────────────────
module "backend" {
  source = "./modules/cloud-run"

  project_id   = var.project_id
  region       = var.region
  service_name = "ai-copilot-backend"
  image        = "${var.region}-docker.pkg.dev/${var.project_id}/${var.artifact_repo_name}/backend:latest"
  service_account_email = module.iam.cloudrun_sa_email

  env_vars = {
    LOG_LEVEL      = "INFO"
    GCP_PROJECT_ID = var.project_id
    GCP_REGION     = var.region
    APP_ENV        = "production"
  }

  secret_env_vars = {
    GROQ_API_KEY   = "${google_secret_manager_secret.groq_api_key.secret_id}:latest"
    GEMINI_API_KEY = "${google_secret_manager_secret.gemini_api_key.secret_id}:latest"
  }

  cpu           = "1"
  memory        = "512Mi"
  min_instances = 0
  max_instances = 5
  concurrency   = 80
  timeout       = 300

  depends_on = [module.iam, google_project_service.apis]
}

# ── Cloud Run — Frontend ──────────────────────────────────────────────────────
module "frontend" {
  source = "./modules/cloud-run"

  project_id   = var.project_id
  region       = var.region
  service_name = "ai-copilot-frontend"
  image        = "${var.region}-docker.pkg.dev/${var.project_id}/${var.artifact_repo_name}/frontend:latest"
  service_account_email = module.iam.cloudrun_sa_email

  env_vars = {
    # VITE_API_URL is baked into the image at build time — not needed at runtime
  }

  secret_env_vars = {}

  cpu           = "1"
  memory        = "256Mi"
  min_instances = 0
  max_instances = 3
  concurrency   = 100
  timeout       = 60

  depends_on = [module.backend, module.iam]
}
