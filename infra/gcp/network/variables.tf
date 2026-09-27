variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region for network resources"
  type        = string
  default     = "us-central1"
}

variable "vpc_name" {
  description = "Name of the VPC network"
  type        = string
  default     = "ai-soc-vpc"
}

variable "subnets" {
  description = "Map of subnet configurations"
  type = map(object({
    region                   = string
    ip_cidr_range            = string
    private_ip_google_access = optional(bool, true)
    secondary_ranges = optional(list(object({
      range_name    = string
      ip_cidr_range = string
    })), [])
    log_config = optional(object({
      aggregation_interval = string
      flow_sampling        = number
      metadata             = string
    }), null)
  }))
  default = {
    gke_nodes = {
      region        = "us-central1"
      ip_cidr_range = "10.1.0.0/20"
      secondary_ranges = [
        {
          range_name    = "gke-pods"
          ip_cidr_range = "10.2.0.0/16"
        },
        {
          range_name    = "gke-services"
          ip_cidr_range = "10.3.0.0/20"
        }
      ]
      log_config = {
        aggregation_interval = "INTERVAL_5_SEC"
        flow_sampling        = 0.5
        metadata             = "INCLUDE_ALL_METADATA"
      }
    }
    management = {
      region        = "us-central1"
      ip_cidr_range = "10.4.0.0/24"
      secondary_ranges = []
    }
    private_services = {
      region        = "us-central1"
      ip_cidr_range = "10.5.0.0/24"
      secondary_ranges = []
    }
  }
}

variable "cloud_nat_min_ports_per_vm" {
  description = "Minimum number of ports allocated per VM for Cloud NAT"
  type        = number
  default     = 64
}

variable "cloud_nat_enable_dynamic_port_allocation" {
  description = "Enable dynamic port allocation for Cloud NAT"
  type        = bool
  default     = true
}

variable "cloud_nat_max_ports_per_vm" {
  description = "Maximum number of ports per VM when dynamic allocation is enabled"
  type        = number
  default     = 4096
}

variable "cloud_nat_log_filter" {
  description = "Log filter for Cloud NAT (ERRORS_ONLY, TRANSLATIONS_ONLY, ALL, NONE)"
  type        = string
  default     = "ERRORS_ONLY"
}

variable "private_service_connect_ip" {
  description = "IP address for Private Service Connect endpoint"
  type        = string
  default     = "10.6.0.2"
}

variable "enable_private_service_access" {
  description = "Enable private service access for managed services (Cloud SQL, Memorystore, etc.)"
  type        = bool
  default     = true
}

variable "private_service_access_cidr" {
  description = "CIDR range for private service access peering"
  type        = string
  default     = "10.100.0.0/16"
}

variable "labels" {
  description = "Labels to apply to all GCP resources"
  type        = map(string)
  default = {
    project     = "ai-agent-soc"
    managed_by  = "terraform"
    environment = "prod"
  }
}
