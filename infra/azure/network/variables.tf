variable "location" {
  description = "Azure region where resources will be deployed"
  type        = string
  default     = "eastus2"
}

variable "resource_group_name" {
  description = "Name of the resource group"
  type        = string
}

variable "vnet_name" {
  description = "Name of the virtual network"
  type        = string
  default     = "ai-soc-vnet"
}

variable "vnet_address_space" {
  description = "Address space for the virtual network"
  type        = list(string)
  default     = ["10.0.0.0/8"]
}

variable "subnets" {
  description = "Map of subnet configurations"
  type = map(object({
    address_prefix    = string
    service_endpoints = optional(list(string), [])
    delegations       = optional(list(object({
      name    = string
      actions = list(string)
    })), [])
  }))
  default = {
    aks_nodes = {
      address_prefix    = "10.1.0.0/16"
      service_endpoints = ["Microsoft.ContainerRegistry", "Microsoft.KeyVault", "Microsoft.Storage"]
    }
    aks_pods = {
      address_prefix    = "10.2.0.0/16"
      service_endpoints = []
    }
    aks_services = {
      address_prefix    = "10.3.0.0/16"
      service_endpoints = []
    }
    management = {
      address_prefix    = "10.4.0.0/24"
      service_endpoints = ["Microsoft.KeyVault"]
    }
    azure_firewall = {
      address_prefix    = "10.4.1.0/26"
      service_endpoints = []
    }
    azure_bastion = {
      address_prefix    = "10.4.2.0/27"
      service_endpoints = []
    }
    private_endpoints = {
      address_prefix    = "10.4.3.0/24"
      service_endpoints = []
    }
  }
}

variable "firewall_sku_tier" {
  description = "SKU tier for Azure Firewall"
  type        = string
  default     = "Premium"
  validation {
    condition     = contains(["Basic", "Standard", "Premium"], var.firewall_sku_tier)
    error_message = "Firewall SKU tier must be Basic, Standard, or Premium."
  }
}

variable "dns_servers" {
  description = "Custom DNS server IP addresses"
  type        = list(string)
  default     = []
}

variable "enable_ddos_protection" {
  description = "Enable DDoS protection plan for the virtual network"
  type        = bool
  default     = false
}

variable "ddos_protection_plan_id" {
  description = "ID of the DDoS protection plan (required if enable_ddos_protection is true)"
  type        = string
  default     = null
}

variable "log_analytics_workspace_id" {
  description = "Log Analytics Workspace ID for diagnostic settings"
  type        = string
  default     = null
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
