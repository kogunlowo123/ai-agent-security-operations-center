###############################################################################
# Core
###############################################################################

variable "location" {
  description = "Azure region for all resources"
  type        = string
  default     = "eastus2"
}

variable "secondary_location" {
  description = "Secondary Azure region for disaster recovery resources"
  type        = string
  default     = "westus2"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "prod"
}

variable "project" {
  description = "Project name"
  type        = string
  default     = "ai-agent-soc"
}

###############################################################################
# Resource Groups
###############################################################################

variable "resource_group_name" {
  description = "Name of the primary resource group"
  type        = string
  default     = "rg-ai-soc-prod"
}

###############################################################################
# Networking
###############################################################################

variable "vnet_address_space" {
  description = "Address space for the virtual network"
  type        = list(string)
  default     = ["10.0.0.0/8"]
}

variable "enable_ddos_protection" {
  description = "Enable DDoS protection plan"
  type        = bool
  default     = false
}

variable "firewall_sku_tier" {
  description = "Azure Firewall SKU tier"
  type        = string
  default     = "Premium"
}

###############################################################################
# AKS
###############################################################################

variable "kubernetes_version" {
  description = "Kubernetes version"
  type        = string
  default     = "1.29"
}

variable "aks_sku_tier" {
  description = "AKS cluster SKU tier"
  type        = string
  default     = "Standard"
}

variable "admin_group_object_ids" {
  description = "List of AAD group object IDs for cluster admins"
  type        = list(string)
  default     = []
}

variable "system_node_pool_node_count" {
  description = "Number of nodes in the system node pool"
  type        = number
  default     = 3
}

variable "user_node_pool_min_count" {
  description = "Minimum user node pool node count"
  type        = number
  default     = 2
}

variable "user_node_pool_max_count" {
  description = "Maximum user node pool node count"
  type        = number
  default     = 20
}

###############################################################################
# Container Registry
###############################################################################

variable "container_registry_sku" {
  description = "SKU for the Azure Container Registry"
  type        = string
  default     = "Premium"
}

###############################################################################
# Monitoring
###############################################################################

variable "log_analytics_retention_days" {
  description = "Log retention in days for Log Analytics workspace"
  type        = number
  default     = 90
}

variable "tags" {
  description = "Tags applied to all resources"
  type        = map(string)
  default     = {}
}
