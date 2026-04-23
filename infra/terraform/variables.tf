# ═══════════════════════════════════════════════════════════════════
#  AI DevOps Copilot — Terraform Variables
# ═══════════════════════════════════════════════════════════════════

variable "project_id" {
  description = "GCP Project ID"
  type        = string

  validation {
    condition     = length(var.project_id) > 0
    error_message = "project_id must not be empty."
  }
}

variable "region" {
  description = "GCP region for all resources"
  type        = string
  default     = "us-central1"

  validation {
    condition = contains([
      "us-central1", "us-east1", "us-west1",
      "europe-west1", "europe-west2",
      "asia-east1", "asia-southeast1"
    ], var.region)
    error_message = "Region must be a valid GCP region."
  }
}

variable "artifact_repo_name" {
  description = "Name of the Artifact Registry repository"
  type        = string
  default     = "copilot"
}

variable "groq_api_key" {
  description = "Groq API key for LLM inference (stored in Secret Manager)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "gemini_api_key" {
  description = "Google Gemini API key (optional fallback LLM)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "backend_min_instances" {
  description = "Minimum Cloud Run instances for backend (0 = scale to zero)"
  type        = number
  default     = 0
}

variable "backend_max_instances" {
  description = "Maximum Cloud Run instances for backend"
  type        = number
  default     = 5
}

variable "environment" {
  description = "Deployment environment (production, staging)"
  type        = string
  default     = "production"

  validation {
    condition     = contains(["production", "staging", "development"], var.environment)
    error_message = "Environment must be: production, staging, or development."
  }
}
