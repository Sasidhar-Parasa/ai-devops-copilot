output "service_url" {
  description = "The public URL of the Cloud Run service"
  value       = google_cloud_run_v2_service.main.uri
}

output "service_name" {
  description = "Cloud Run service name"
  value       = google_cloud_run_v2_service.main.name
}

output "latest_revision" {
  description = "Name of the latest revision"
  value       = google_cloud_run_v2_service.main.latest_ready_revision
}
