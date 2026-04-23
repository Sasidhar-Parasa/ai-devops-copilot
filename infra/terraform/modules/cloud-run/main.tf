# ═══════════════════════════════════════════════════════════════════
#  Module: Cloud Run Service
#  Creates a production-ready Cloud Run service with:
#  - Secret Manager integration
#  - Custom service account
#  - Auto-scaling configuration
#  - Public access (IAM policy)
# ═══════════════════════════════════════════════════════════════════

resource "google_cloud_run_v2_service" "main" {
  name     = var.service_name
  location = var.region
  project  = var.project_id

  # Ingress: allow all traffic (public service)
  ingress = "INGRESS_TRAFFIC_ALL"

  template {
    # Use dedicated service account (least privilege)
    service_account = var.service_account_email

    # Auto-scaling
    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    # Startup probe — wait for app to be ready before sending traffic
    containers {
      image = var.image
      name  = var.service_name

      # Resource limits (per container instance)
      resources {
        limits = {
          cpu    = var.cpu
          memory = var.memory
        }
        # CPU always allocated (not throttled when idle) = better cold start
        # Set to false to reduce cost with startup latency trade-off
        cpu_idle          = true   # throttle CPU when no requests
        startup_cpu_boost = true   # full CPU during startup for faster cold starts
      }

      # Port Cloud Run routes traffic to
      ports {
        container_port = 8080
        name           = "http1"
      }

      # Plain environment variables
      dynamic "env" {
        for_each = var.env_vars
        content {
          name  = env.key
          value = env.value
        }
      }

      # Secret Manager environment variables
      dynamic "env" {
        for_each = var.secret_env_vars
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = split(":", env.value)[0]
              version = split(":", env.value)[1]
            }
          }
        }
      }

      # Liveness probe — restart container if unhealthy
      liveness_probe {
        http_get {
          path = "/api/ping"
          port = 8080
        }
        initial_delay_seconds = 15
        period_seconds        = 30
        failure_threshold     = 3
        timeout_seconds       = 5
      }

      # Startup probe — give app time to initialize
      startup_probe {
        http_get {
          path = "/api/ping"
          port = 8080
        }
        initial_delay_seconds = 5
        period_seconds        = 5
        failure_threshold     = 12   # 60s total startup time
        timeout_seconds       = 3
      }
    }

    # Max concurrent requests per instance
    max_instance_request_concurrency = var.concurrency

    # Request timeout
    timeout = "${var.timeout}s"

    labels = {
      managed-by  = "terraform"
      environment = "production"
      service     = var.service_name
    }
  }

  # Traffic routing — send 100% to latest revision
  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  labels = {
    managed-by = "terraform"
    project    = "ai-devops-copilot"
  }

  lifecycle {
    # Allow GitHub Actions to update the image without Terraform conflicts
    ignore_changes = [
      template[0].containers[0].image,
      template[0].labels,
      labels,
    ]
  }
}

# ── Allow unauthenticated access (public) ─────────────────────────────────────
resource "google_cloud_run_v2_service_iam_member" "public_access" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.main.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
