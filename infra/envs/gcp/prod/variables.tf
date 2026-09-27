###############################################################################
# Core
###############################################################################

variable "project_id" {
  description = "GCP project ID where resources will be deployed"
  type        = string
}

variable "region" {
  description = "Primary GCP region for all resources"
  type        = string
  default     = "us-central1"
}

variable "secondary_region" {
  description = "Secondary GCP region for disaster recovery"
  type        = string
  default     = "us-east1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "prod"
}

variable "project_name" {
  description = "Short project name used in resource naming"
  type        = string
  default     = "ai-soc"
}

###############################################################################
# Networking
###############################################################################

variable "vpc_name" {
  description = "Name of the VPC network"
  type        = string
  default     = "ai-soc-vpc-prod"
}

variable "gke_nodes_cidr" {
  description = "CIDR for the GKE nodes subnet"
  type        = string
  default     = "10.1.0.0/20"
}

variable "gke_pods_cidr" {
  description = "CIDR for the GKE pods secondary range"
  type        = string
  default     = "10.2.0.0/16"
}

variable "gke_services_cidr" {
  description = "CIDR for the GKE services secondary range"
  type        = string
  default     = "10.3.0.0/20"
}

variable "enable_private_service_access" {
  description = "Enable private service access for Cloud SQL, Memorystore, etc."
  type        = bool
  default     = true
}

###############################################################################
# GKE
###############################################################################

variable "cluster_name" {
  description = "Name of the GKE Autopilot cluster"
  type        = string
  default     = "ai-soc-gke-prod"
}

variable "master_ipv4_cidr_block" {
  description = "CIDR block for the GKE master nodes (/28)"
  type        = string
  default     = "172.16.0.0/28"
}

variable "master_authorized_networks" {
  description = "CIDRs authorized to access the Kubernetes master"
  type = list(object({
    cidr_block   = string
    display_name = string
  }))
  default = []
}

variable "release_channel" {
  description = "GKE release channel"
  type        = string
  default     = "REGULAR"
}

variable "enable_binary_authorization" {
  description = "Enable Binary Authorization"
  type        = bool
  default     = true
}

variable "enable_config_connector" {
  description = "Enable Config Connector addon"
  type        = bool
  default     = true
}

variable "deletion_protection" {
  description = "Prevent accidental deletion of the cluster"
  type        = bool
  default     = true
}

###############################################################################
# Artifact Registry
###############################################################################

variable "artifact_registry_location" {
  description = "Location for the Artifact Registry repository"
  type        = string
  default     = "us-central1"
}

###############################################################################
# Monitoring
###############################################################################

variable "log_retention_days" {
  description = "Log retention in days for Cloud Logging sinks"
  type        = number
  default     = 90
}

variable "labels" {
  description = "Labels applied to all GCP resources"
  type        = map(string)
  default     = {}
}
