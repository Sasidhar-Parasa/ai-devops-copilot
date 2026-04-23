# ═══════════════════════════════════════════════════════════════════
#  Module: Artifact Registry
# ═══════════════════════════════════════════════════════════════════

resource "google_artifact_registry_repository" "main" {
  provider = google

  project       = var.project_id
  location      = var.region
  repository_id = var.repo_name
  description   = var.description
  format        = "DOCKER"

  # Automatically clean up old images to save storage costs
  cleanup_policies {
    id     = "keep-last-10"
    action = "KEEP"
    most_recent_versions {
      keep_count = 10
    }
  }

  cleanup_policies {
    id     = "delete-old"
    action = "DELETE"
    condition {
      older_than = "2592000s"  # 30 days
      tag_state  = "UNTAGGED"
    }
  }

  labels = {
    managed-by  = "terraform"
    project     = "ai-devops-copilot"
    environment = "production"
  }
}
