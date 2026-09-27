variable "location" {
  description = "Azure region where the AKS cluster will be deployed"
  type        = string
  default     = "eastus2"
}

variable "resource_group_name" {
  description = "Name of the resource group containing the AKS cluster"
  type        = string
}

variable "cluster_name" {
  description = "Name of the AKS cluster"
  type        = string
  default     = "ai-soc-aks"
}

variable "kubernetes_version" {
  description = "Kubernetes version for the AKS cluster"
  type        = string
  default     = "1.29"
}

variable "sku_tier" {
  description = "AKS cluster SKU tier (Free, Standard, or Premium)"
  type        = string
  default     = "Standard"
  validation {
    condition     = contains(["Free", "Standard", "Premium"], var.sku_tier)
    error_message = "SKU tier must be Free, Standard, or Premium."
  }
}

variable "dns_prefix" {
  description = "DNS prefix for the AKS cluster"
  type        = string
  default     = "ai-soc"
}

# System node pool
variable "system_node_pool_name" {
  description = "Name of the system node pool"
  type        = string
  default     = "systempool"
}

variable "system_node_pool_vm_size" {
  description = "VM size for system node pool nodes"
  type        = string
  default     = "Standard_D4s_v3"
}

variable "system_node_pool_node_count" {
  description = "Number of nodes in the system node pool"
  type        = number
  default     = 3
}

variable "system_node_pool_os_disk_size_gb" {
  description = "OS disk size (GB) for system node pool"
  type        = number
  default     = 128
}

variable "system_node_pool_max_pods" {
  description = "Maximum number of pods per node in the system pool"
  type        = number
  default     = 30
}

variable "system_node_pool_availability_zones" {
  description = "Availability zones for the system node pool"
  type        = list(string)
  default     = ["1", "2", "3"]
}

# User node pool
variable "user_node_pool_name" {
  description = "Name of the user node pool"
  type        = string
  default     = "userpool"
}

variable "user_node_pool_vm_size" {
  description = "VM size for user node pool nodes"
  type        = string
  default     = "Standard_D8s_v3"
}

variable "user_node_pool_min_count" {
  description = "Minimum number of nodes for autoscaling in the user pool"
  type        = number
  default     = 2
}

variable "user_node_pool_max_count" {
  description = "Maximum number of nodes for autoscaling in the user pool"
  type        = number
  default     = 20
}

variable "user_node_pool_initial_count" {
  description = "Initial number of nodes in the user pool"
  type        = number
  default     = 3
}

variable "user_node_pool_os_disk_size_gb" {
  description = "OS disk size (GB) for user node pool"
  type        = number
  default     = 128
}

variable "user_node_pool_max_pods" {
  description = "Maximum number of pods per node in the user pool"
  type        = number
  default     = 60
}

variable "user_node_pool_availability_zones" {
  description = "Availability zones for the user node pool"
  type        = list(string)
  default     = ["1", "2", "3"]
}

variable "user_node_pool_node_labels" {
  description = "Labels to apply to user node pool nodes"
  type        = map(string)
  default = {
    "workload-type" = "ai-agent"
    "pool"          = "user"
  }
}

variable "user_node_pool_node_taints" {
  description = "Taints to apply to user node pool nodes"
  type        = list(string)
  default     = []
}

# Networking
variable "vnet_subnet_id" {
  description = "Resource ID of the subnet for AKS nodes"
  type        = string
}

variable "pod_subnet_id" {
  description = "Resource ID of the subnet for AKS pods (Azure CNI overlay)"
  type        = string
  default     = null
}

variable "service_cidr" {
  description = "CIDR range for Kubernetes services"
  type        = string
  default     = "172.16.0.0/16"
}

variable "dns_service_ip" {
  description = "IP address for the Kubernetes DNS service (must be within service_cidr)"
  type        = string
  default     = "172.16.0.10"
}

variable "network_plugin" {
  description = "Network plugin for AKS (azure or kubenet)"
  type        = string
  default     = "azure"
}

variable "network_policy" {
  description = "Network policy for AKS (azure, calico, or cilium)"
  type        = string
  default     = "azure"
}

variable "outbound_type" {
  description = "Outbound type for AKS cluster (userDefinedRouting, loadBalancer)"
  type        = string
  default     = "userDefinedRouting"
}

variable "private_cluster_enabled" {
  description = "Enable private cluster mode (API server accessible only via private endpoint)"
  type        = bool
  default     = true
}

variable "private_dns_zone_id" {
  description = "ID of the private DNS zone for the AKS private cluster"
  type        = string
  default     = "System"
}

# Azure AD / RBAC
variable "admin_group_object_ids" {
  description = "List of AAD group object IDs that will have admin access to the cluster"
  type        = list(string)
  default     = []
}

variable "azure_rbac_enabled" {
  description = "Enable Azure RBAC for Kubernetes authorization"
  type        = bool
  default     = true
}

# Identity
variable "identity_type" {
  description = "Type of identity for the cluster (SystemAssigned or UserAssigned)"
  type        = string
  default     = "UserAssigned"
}

variable "user_assigned_identity_id" {
  description = "Resource ID of the user-assigned managed identity (required if identity_type is UserAssigned)"
  type        = string
  default     = null
}

variable "kubelet_identity_client_id" {
  description = "Client ID of the kubelet identity"
  type        = string
  default     = null
}

variable "kubelet_identity_object_id" {
  description = "Object ID of the kubelet identity"
  type        = string
  default     = null
}

variable "kubelet_identity_user_assigned_identity_id" {
  description = "Resource ID of the user-assigned identity for kubelet"
  type        = string
  default     = null
}

# Add-ons
variable "azure_policy_enabled" {
  description = "Enable Azure Policy add-on for AKS"
  type        = bool
  default     = true
}

variable "oms_agent_enabled" {
  description = "Enable OMS agent for Azure Monitor"
  type        = bool
  default     = true
}

variable "log_analytics_workspace_id" {
  description = "Log Analytics Workspace ID for OMS agent"
  type        = string
  default     = null
}

variable "key_vault_secrets_provider_enabled" {
  description = "Enable Azure Key Vault secrets provider"
  type        = bool
  default     = true
}

variable "secret_rotation_enabled" {
  description = "Enable automatic secret rotation for Key Vault secrets provider"
  type        = bool
  default     = true
}

variable "secret_rotation_interval" {
  description = "Interval for secret rotation"
  type        = string
  default     = "2m"
}

# Container Registry
variable "container_registry_id" {
  description = "Resource ID of the Azure Container Registry to grant AKS pull access"
  type        = string
  default     = null
}

variable "maintenance_window_start_hour" {
  description = "Start hour for the AKS maintenance window (0-23 UTC)"
  type        = number
  default     = 2
}

variable "maintenance_window_day" {
  description = "Day for the AKS maintenance window"
  type        = string
  default     = "Sunday"
}

variable "auto_upgrade_channel" {
  description = "Auto-upgrade channel for AKS (patch, rapid, stable, node-image, or none)"
  type        = string
  default     = "stable"
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default = {
    project     = "ai-agent-soc"
    managed_by  = "terraform"
    environment = "prod"
  }
}
