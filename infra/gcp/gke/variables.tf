variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region for the GKE cluster"
  type        = string
  default     = "us-central1"
}

variable "cluster_name" {
  description = "Name of the GKE cluster"
  type        = string
  default     = "ai-soc-gke"
}

variable "network" {
  description = "VPC network name or self-link for the GKE cluster"
  type        = string
}

variable "subnetwork" {
  description = "Subnetwork name or self-link for GKE nodes"
  type        = string
}

variable "pods_secondary_range_name" {
  description = "Name of the secondary range for GKE pods"
  type        = string
}

variable "services_secondary_range_name" {
  description = "Name of the secondary range for GKE services"
  type        = string
}

variable "master_ipv4_cidr_block" {
  description = "CIDR block for the GKE control plane (must be /28)"
  type        = string
  default     = "172.16.0.0/28"
}

variable "master_authorized_networks" {
  description = "List of CIDRs authorized to access the Kubernetes master endpoint"
  type = list(object({
    cidr_block   = string
    display_name = string
  }))
  default = []
}

variable "deletion_protection" {
  description = "Prevent accidental deletion of the cluster"
  type        = bool
  default     = true
}

variable "release_channel" {
  description = "GKE release channel (RAPID, REGULAR, STABLE)"
  type        = string
  default     = "REGULAR"
  validation {
    condition     = contains(["RAPID", "REGULAR", "STABLE", "EXTENDED", "UNSPECIFIED"], var.release_channel)
    error_message = "Release channel must be RAPID, REGULAR, STABLE, EXTENDED, or UNSPECIFIED."
  }
}

variable "enable_workload_identity" {
  description = "Enable Workload Identity on the cluster"
  type        = bool
  default     = true
}

variable "enable_binary_authorization" {
  description = "Enable Binary Authorization for container image verification"
  type        = bool
  default     = true
}

variable "binary_authorization_evaluation_mode" {
  description = "Binary Authorization evaluation mode (DISABLED, PROJECT_SINGLETON_POLICY_ENFORCE)"
  type        = string
  default     = "PROJECT_SINGLETON_POLICY_ENFORCE"
}

variable "enable_shielded_nodes" {
  description = "Enable Shielded Nodes features (secure boot, vTPM, integrity monitoring)"
  type        = bool
  default     = true
}

variable "enable_config_connector" {
  description = "Enable Config Connector addon to manage GCP resources via Kubernetes"
  type        = bool
  default     = true
}

variable "enable_network_policy" {
  description = "Enable Kubernetes network policy enforcement"
  type        = bool
  default     = true
}

variable "enable_dataplane_v2" {
  description = "Enable GKE Dataplane V2 (eBPF-based networking via Cilium)"
  type        = bool
  default     = true
}

variable "enable_http_load_balancing" {
  description = "Enable HTTP load balancing addon"
  type        = bool
  default     = true
}

variable "enable_horizontal_pod_autoscaling" {
  description = "Enable Horizontal Pod Autoscaling addon"
  type        = bool
  default     = true
}

variable "enable_dns_cache" {
  description = "Enable NodeLocal DNSCache addon"
  type        = bool
  default     = true
}

variable "enable_gce_persistent_disk_csi_driver" {
  description = "Enable GCE persistent disk CSI driver"
  type        = bool
  default     = true
}

variable "enable_gcs_fuse_csi_driver" {
  description = "Enable GCS FUSE CSI driver"
  type        = bool
  default     = false
}

variable "private_cluster_enabled" {
  description = "Enable private cluster mode (nodes have no public IPs)"
  type        = bool
  default     = true
}

variable "enable_private_endpoint" {
  description = "Enable private endpoint (master accessible only via private IP)"
  type        = bool
  default     = true
}

variable "maintenance_start_time" {
  description = "Start time for the GKE maintenance window in RFC3339 format"
  type        = string
  default     = "2023-01-01T02:00:00Z"
}

variable "maintenance_end_time" {
  description = "End time for the GKE maintenance window"
  type        = string
  default     = "2023-01-01T06:00:00Z"
}

variable "maintenance_recurrence" {
  description = "Recurrence rule for maintenance window (RFC5545 RRULE)"
  type        = string
  default     = "FREQ=WEEKLY;BYDAY=SA,SU"
}

variable "log_config_components" {
  description = "GKE log components to enable"
  type        = list(string)
  default = [
    "SYSTEM_COMPONENTS",
    "WORKLOADS",
    "APISERVER",
    "CONTROLLER_MANAGER",
    "SCHEDULER",
  ]
}

variable "monitoring_components" {
  description = "GKE monitoring components to enable"
  type        = list(string)
  default = [
    "SYSTEM_COMPONENTS",
    "WORKLOADS",
    "APISERVER",
    "CONTROLLER_MANAGER",
    "SCHEDULER",
    "DAEMONSET",
    "DEPLOYMENT",
    "STATEFULSET",
  ]
}

variable "labels" {
  description = "Labels to apply to the GKE cluster"
  type        = map(string)
  default = {
    project     = "ai-agent-soc"
    managed_by  = "terraform"
    environment = "prod"
  }
}
