# ═══════════════════════════════════════════════════════════════════
#  AI DevOps Copilot — Terraform Outputs
# ═══════════════════════════════════════════════════════════════════

output "backend_url" {
  description = "Backend Cloud Run service URL"
  value       = module.backend.service_url
}

output "frontend_url" {
  description = "Frontend Cloud Run service URL (submit this for demo)"
  value       = module.frontend.service_url
}

output "artifact_registry_url" {
  description = "Artifact Registry repository URL"
  value       = module.artifact_registry.registry_url
}

output "cicd_service_account_email" {
  description = "Service account email to use as GCP_SA_KEY in GitHub Secrets"
  value       = module.iam.cicd_sa_email
}

output "cloudrun_service_account_email" {
  description = "Service account used by Cloud Run services"
  value       = module.iam.cloudrun_sa_email
}

output "api_docs_url" {
  description = "FastAPI Swagger docs URL"
  value       = "${module.backend.service_url}/docs"
}

output "health_check_url" {
  description = "Backend health check endpoint"
  value       = "${module.backend.service_url}/api/ping"
}

output "github_secrets_needed" {
  description = "GitHub secrets you need to configure"
  value = {
    GCP_PROJECT_ID = var.project_id
    GCP_REGION     = var.region
    GCP_SA_KEY     = "Run: terraform output -raw cicd_sa_key_json"
  }
}

output "cicd_sa_key_json" {
  description = "Service Account key JSON for GitHub Actions"
  value       = module.iam.cicd_sa_key_json
  sensitive   = true
}
