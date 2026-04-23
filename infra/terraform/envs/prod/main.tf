# ═══════════════════════════════════════════════════════════════════
#  Production environment — calls root module with prod values
#  Usage: cd infra/terraform/envs/prod && terraform init && terraform apply
#
#  This pattern lets you have staging/ and prod/ environments
#  using the same root module with different variable values.
# ═══════════════════════════════════════════════════════════════════

terraform {
  required_version = ">= 1.6"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  # Separate state for prod environment
  backend "gcs" {
    bucket = "REPLACE_WITH_YOUR_PROJECT_ID-tf-state"
    prefix = "ai-devops-copilot/envs/prod"
  }
}

# Call the root module from this environment directory
module "root" {
  source = "../../"   # points to infra/terraform/

  # ── Required ──────────────────────────────────────────────────
  project_id = var.project_id
  region     = var.region

  # ── Secrets ───────────────────────────────────────────────────
  groq_api_key   = var.groq_api_key
  gemini_api_key = var.gemini_api_key

  # ── Production-specific scaling ───────────────────────────────
  backend_min_instances = 1    # Keep 1 warm to eliminate cold starts
  backend_max_instances = 10   # Handle traffic spikes

  environment        = "production"
  artifact_repo_name = "copilot"
}

# ── Variables (override root defaults for prod) ───────────────────
variable "project_id"    { type = string }
variable "region"        { type = string; default = "us-central1" }
variable "groq_api_key"  { type = string; sensitive = true; default = "" }
variable "gemini_api_key" { type = string; sensitive = true; default = "" }

# ── Pass-through outputs ──────────────────────────────────────────
output "backend_url"  { value = module.root.backend_url }
output "frontend_url" { value = module.root.frontend_url }
output "registry_url" { value = module.root.artifact_registry_url }
