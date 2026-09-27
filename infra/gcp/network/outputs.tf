output "vpc_id" {
  description = "The self-link of the VPC network"
  value       = google_compute_network.this.id
}

output "vpc_name" {
  description = "The name of the VPC network"
  value       = google_compute_network.this.name
}

output "vpc_self_link" {
  description = "The self-link URL of the VPC network"
  value       = google_compute_network.this.self_link
}

output "subnet_ids" {
  description = "Map of subnet names to their self-link IDs"
  value       = { for k, v in google_compute_subnetwork.this : k => v.id }
}

output "subnet_self_links" {
  description = "Map of subnet names to their self-link URLs"
  value       = { for k, v in google_compute_subnetwork.this : k => v.self_link }
}

output "subnet_regions" {
  description = "Map of subnet names to their regions"
  value       = { for k, v in google_compute_subnetwork.this : k => v.region }
}

output "subnet_secondary_ranges" {
  description = "Map of subnet names to their secondary IP range names"
  value = {
    for k, v in google_compute_subnetwork.this : k => {
      for r in v.secondary_ip_range : r.range_name => r.ip_cidr_range
    }
  }
}

output "cloud_router_id" {
  description = "The ID of the Cloud Router"
  value       = google_compute_router.this.id
}

output "cloud_router_name" {
  description = "The name of the Cloud Router"
  value       = google_compute_router.this.name
}

output "cloud_nat_id" {
  description = "The ID of the Cloud NAT"
  value       = google_compute_router_nat.this.id
}

output "private_service_access_address" {
  description = "IP address reserved for private service access"
  value       = length(google_compute_global_address.private_service_access) > 0 ? google_compute_global_address.private_service_access[0].address : null
}

output "psc_google_apis_ip" {
  description = "IP address of the Private Service Connect endpoint for Google APIs"
  value       = google_compute_global_address.psc_google_apis.address
}

output "gke_pods_secondary_range_name" {
  description = "Secondary range name for GKE pods (in gke_nodes subnet)"
  value       = contains(keys(var.subnets), "gke_nodes") ? try(var.subnets["gke_nodes"].secondary_ranges[0].range_name, null) : null
}

output "gke_services_secondary_range_name" {
  description = "Secondary range name for GKE services (in gke_nodes subnet)"
  value       = contains(keys(var.subnets), "gke_nodes") ? try(var.subnets["gke_nodes"].secondary_ranges[1].range_name, null) : null
}
