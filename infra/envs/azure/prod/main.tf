terraform {
  required_version = ">= 1.5.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 2.0"
    }
  }
}

provider "azurerm" {
  features {
    resource_group {
      prevent_deletion_if_contains_resources = true
    }
    key_vault {
      purge_soft_delete_on_destroy               = false
      recover_soft_deleted_key_vaults            = true
      purge_soft_deleted_secrets_on_destroy      = false
      purge_soft_deleted_certificates_on_destroy = false
    }
  }
}

provider "azuread" {}

###############################################################################
# Locals
###############################################################################

locals {
  common_tags = merge(
    {
      project     = var.project
      environment = var.environment
      managed_by  = "terraform"
      repo        = "ai-agent-security-operations-center"
    },
    var.tags
  )
}

###############################################################################
# Resource Groups
###############################################################################

resource "azurerm_resource_group" "main" {
  name     = var.resource_group_name
  location = var.location
  tags     = local.common_tags
}

resource "azurerm_resource_group" "monitoring" {
  name     = "${var.resource_group_name}-monitoring"
  location = var.location
  tags     = local.common_tags
}

###############################################################################
# Log Analytics Workspace
###############################################################################

resource "azurerm_log_analytics_workspace" "this" {
  name                = "law-${var.project}-${var.environment}"
  location            = azurerm_resource_group.monitoring.location
  resource_group_name = azurerm_resource_group.monitoring.name
  sku                 = "PerGB2018"
  retention_in_days   = var.log_analytics_retention_days
  tags                = merge(local.common_tags, { component = "monitoring" })
}

resource "azurerm_log_analytics_solution" "container_insights" {
  solution_name         = "ContainerInsights"
  location              = azurerm_resource_group.monitoring.location
  resource_group_name   = azurerm_resource_group.monitoring.name
  workspace_resource_id = azurerm_log_analytics_workspace.this.id
  workspace_name        = azurerm_log_analytics_workspace.this.name

  plan {
    publisher = "Microsoft"
    product   = "OMSGallery/ContainerInsights"
  }
}

###############################################################################
# Azure Container Registry
###############################################################################

resource "azurerm_container_registry" "this" {
  name                = "cracaisoc${var.environment}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = var.container_registry_sku
  admin_enabled       = false

  network_rule_set {
    default_action = "Deny"
  }

  georeplications {
    location                = var.secondary_location
    zone_redundancy_enabled = true
    tags                    = local.common_tags
  }

  retention_policy {
    days    = 30
    enabled = true
  }

  trust_policy {
    enabled = true
  }

  zone_redundancy_enabled = true
  tags                    = merge(local.common_tags, { component = "acr" })
}

###############################################################################
# Key Vault
###############################################################################

data "azurerm_client_config" "current" {}

resource "azurerm_key_vault" "this" {
  name                        = "kv-ai-soc-${var.environment}"
  location                    = azurerm_resource_group.main.location
  resource_group_name         = azurerm_resource_group.main.name
  tenant_id                   = data.azurerm_client_config.current.tenant_id
  sku_name                    = "premium"
  purge_protection_enabled    = true
  soft_delete_retention_days  = 90
  enable_rbac_authorization   = true

  network_acls {
    default_action = "Deny"
    bypass         = "AzureServices"
    ip_rules       = []
  }

  tags = merge(local.common_tags, { component = "key-vault" })
}

###############################################################################
# Network Module
###############################################################################

module "network" {
  source = "../../../azure/network"

  location            = var.location
  resource_group_name = azurerm_resource_group.main.name
  vnet_name           = "vnet-${var.project}-${var.environment}"
  vnet_address_space  = var.vnet_address_space

  firewall_sku_tier          = var.firewall_sku_tier
  enable_ddos_protection     = var.enable_ddos_protection
  log_analytics_workspace_id = azurerm_log_analytics_workspace.this.id

  tags = local.common_tags

  depends_on = [azurerm_resource_group.main]
}

###############################################################################
# AKS Module
###############################################################################

module "aks" {
  source = "../../../azure/aks"

  location            = var.location
  resource_group_name = azurerm_resource_group.main.name
  cluster_name        = "aks-${var.project}-${var.environment}"
  dns_prefix          = "${var.project}-${var.environment}"
  kubernetes_version  = var.kubernetes_version
  sku_tier            = var.aks_sku_tier

  # Networking
  vnet_subnet_id = module.network.subnet_ids["aks_nodes"]
  pod_subnet_id  = module.network.subnet_ids["aks_pods"]
  outbound_type  = "userDefinedRouting"

  # System node pool
  system_node_pool_node_count         = var.system_node_pool_node_count
  system_node_pool_availability_zones = ["1", "2", "3"]

  # User node pool
  user_node_pool_min_count = var.user_node_pool_min_count
  user_node_pool_max_count = var.user_node_pool_max_count

  # Azure AD
  admin_group_object_ids = var.admin_group_object_ids
  azure_rbac_enabled     = true

  # Add-ons
  azure_policy_enabled               = true
  oms_agent_enabled                  = true
  log_analytics_workspace_id         = azurerm_log_analytics_workspace.this.id
  key_vault_secrets_provider_enabled = true
  secret_rotation_enabled            = true

  # Container Registry
  container_registry_id = azurerm_container_registry.this.id

  # Private cluster
  private_cluster_enabled = true

  tags = local.common_tags

  depends_on = [module.network]
}

###############################################################################
# Key Vault Role Assignments for AKS
###############################################################################

resource "azurerm_role_assignment" "aks_kv_secrets_user" {
  scope                = azurerm_key_vault.this.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = module.aks.kubelet_identity_object_id
}
