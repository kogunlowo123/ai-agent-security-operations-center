output "cluster_id" {
  description = "The unique identifier of the GKE cluster"
  value       = google_container_cluster.this.id
}

output "cluster_name" {
  description = "The name of the GKE cluster"
  value       = google_container_cluster.this.name
}

output "cluster_location" {
  description = "The location (region or zone) of the GKE cluster"
  value       = google_container_cluster.this.location
}

output "cluster_self_link" {
  description = "The server-defined URL of the GKE cluster"
  value       = google_container_cluster.this.self_link
}

output "cluster_endpoint" {
  description = "The IP address of the Kubernetes master endpoint"
  value       = google_container_cluster.this.endpoint
  sensitive   = true
}

output "cluster_ca_certificate" {
  description = "Base64-encoded CA certificate for the Kubernetes master"
  value       = google_container_cluster.this.master_auth[0].cluster_ca_certificate
  sensitive   = true
}

output "workload_identity_pool" {
  description = "Workload Identity pool name for IAM bindings"
  value       = var.enable_workload_identity ? "${var.project_id}.svc.id.goog" : null
}

output "kms_key_ring_id" {
  description = "Resource ID of the KMS key ring"
  value       = google_kms_key_ring.this.id
}

output "kms_crypto_key_id" {
  description = "Resource ID of the KMS crypto key for cluster secrets"
  value       = google_kms_crypto_key.cluster_secrets.id
}

output "config_connector_service_account_email" {
  description = "Email of the Config Connector Google Service Account"
  value       = length(google_service_account.config_connector) > 0 ? google_service_account.config_connector[0].email : null
}

output "cluster_notifications_topic" {
  description = "Pub/Sub topic ID for cluster upgrade notifications"
  value       = google_pubsub_topic.cluster_notifications.id
}

output "master_version" {
  description = "The current version of the master Kubernetes API"
  value       = data.google_container_cluster.this.master_version
}
