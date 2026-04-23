output "cicd_sa_email" {
  description = "CI/CD service account email (for reference)"
  value       = google_service_account.cicd.email
}

output "cicd_sa_key_json" {
  description = "CI/CD SA JSON key — add this as GCP_SA_KEY in GitHub Secrets"
  value       = base64decode(google_service_account_key.cicd.private_key)
  sensitive   = true
}

output "cloudrun_sa_email" {
  description = "Cloud Run runtime service account email"
  value       = google_service_account.cloudrun.email
}
