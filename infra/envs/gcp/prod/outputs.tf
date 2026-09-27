###############################################################################
# Network Outputs
###############################################################################

output "vpc_id" {
  description = "The ID of the VPC network"
  value       = module.network.vpc_id
}

output "vpc_name" {
  description = "The name of the VPC network"
  value       = module.network.vpc_name
}

output "vpc_self_link" {
  description = "The self-link of the VPC network"
  value       = module.network.vpc_self_link
}

output "subnet_ids" {
  description = "Map of subnet names to their IDs"
  value       = module.network.subnet_ids
}

output "subnet_self_links" {
  description = "Map of subnet names to their self-link URLs"
  value       = module.network.subnet_self_links
}

output "cloud_nat_id" {
  description = "ID of the Cloud NAT resource"
  value       = module.network.cloud_nat_id
}

output "psc_google_apis_ip" {
  description = "Private Service Connect IP for Google APIs"
  value       = module.network.psc_google_apis_ip
}

###############################################################################
# GKE Outputs
###############################################################################

output "gke_cluster_id" {
  description = "The ID of the GKE cluster"
  value       = module.gke.cluster_id
}

output "gke_cluster_name" {
  description = "The name of the GKE cluster"
  value       = module.gke.cluster_name
}

output "gke_cluster_location" {
  description = "The location of the GKE cluster"
  value       = module.gke.cluster_location
}

output "gke_cluster_endpoint" {
  description = "The endpoint of the GKE master"
  value       = module.gke.cluster_endpoint
  sensitive   = true
}

output "gke_cluster_ca_certificate" {
  description = "Base64-encoded CA certificate for the GKE cluster"
  value       = module.gke.cluster_ca_certificate
  sensitive   = true
}

output "gke_workload_identity_pool" {
  description = "Workload Identity pool for GKE"
  value       = module.gke.workload_identity_pool
}

output "gke_kms_crypto_key_id" {
  description = "KMS crypto key ID used for GKE secret encryption"
  value       = module.gke.kms_crypto_key_id
}

output "gke_config_connector_sa_email" {
  description = "Config Connector service account email"
  value       = module.gke.config_connector_service_account_email
}

###############################################################################
# Artifact Registry Outputs
###############################################################################

output "artifact_registry_id" {
  description = "The ID of the Artifact Registry repository"
  value       = google_artifact_registry_repository.this.id
}

output "artifact_registry_name" {
  description = "Full name of the Artifact Registry repository"
  value       = google_artifact_registry_repository.this.name
}

output "artifact_registry_location" {
  description = "Location of the Artifact Registry repository"
  value       = google_artifact_registry_repository.this.location
}

###############################################################################
# Binary Authorization Outputs
###############################################################################

output "binary_authorization_policy_id" {
  description = "The ID of the Binary Authorization policy"
  value       = length(google_binary_authorization_policy.this) > 0 ? google_binary_authorization_policy.this[0].id : null
}
