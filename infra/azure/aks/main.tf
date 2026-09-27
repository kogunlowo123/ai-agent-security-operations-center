terraform {
  required_version = ">= 1.5.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

###############################################################################
# User-Assigned Managed Identity for AKS control plane
###############################################################################

resource "azurerm_user_assigned_identity" "aks_control_plane" {
  count = var.identity_type == "UserAssigned" && var.user_assigned_identity_id == null ? 1 : 0

  name                = "mi-${var.cluster_name}-cp"
  location            = var.location
  resource_group_name = var.resource_group_name
  tags                = merge(var.tags, { component = "aks-identity" })
}

resource "azurerm_user_assigned_identity" "aks_kubelet" {
  count = var.kubelet_identity_user_assigned_identity_id == null ? 1 : 0

  name                = "mi-${var.cluster_name}-kubelet"
  location            = var.location
  resource_group_name = var.resource_group_name
  tags                = merge(var.tags, { component = "aks-identity" })
}

locals {
  control_plane_identity_id = var.user_assigned_identity_id != null ? var.user_assigned_identity_id : (
    length(azurerm_user_assigned_identity.aks_control_plane) > 0
    ? azurerm_user_assigned_identity.aks_control_plane[0].id
    : null
  )
  kubelet_identity_id = var.kubelet_identity_user_assigned_identity_id != null ? var.kubelet_identity_user_assigned_identity_id : (
    length(azurerm_user_assigned_identity.aks_kubelet) > 0
    ? azurerm_user_assigned_identity.aks_kubelet[0].id
    : null
  )
  kubelet_client_id = var.kubelet_identity_client_id != null ? var.kubelet_identity_client_id : (
    length(azurerm_user_assigned_identity.aks_kubelet) > 0
    ? azurerm_user_assigned_identity.aks_kubelet[0].client_id
    : null
  )
  kubelet_object_id = var.kubelet_identity_object_id != null ? var.kubelet_identity_object_id : (
    length(azurerm_user_assigned_identity.aks_kubelet) > 0
    ? azurerm_user_assigned_identity.aks_kubelet[0].principal_id
    : null
  )
}

###############################################################################
# Role Assignments
###############################################################################

# Grant AKS control plane identity Network Contributor on the subnet
resource "azurerm_role_assignment" "aks_network_contributor" {
  scope                = var.vnet_subnet_id
  role_definition_name = "Network Contributor"
  principal_id = (
    length(azurerm_user_assigned_identity.aks_control_plane) > 0
    ? azurerm_user_assigned_identity.aks_control_plane[0].principal_id
    : null
  )
}

# Grant kubelet identity ACR pull access if ACR ID provided
resource "azurerm_role_assignment" "aks_acr_pull" {
  count = var.container_registry_id != null ? 1 : 0

  scope                = var.container_registry_id
  role_definition_name = "AcrPull"
  principal_id         = local.kubelet_object_id
}

###############################################################################
# AKS Cluster
###############################################################################

resource "azurerm_kubernetes_cluster" "this" {
  name                = var.cluster_name
  location            = var.location
  resource_group_name = var.resource_group_name
  dns_prefix          = var.dns_prefix
  kubernetes_version  = var.kubernetes_version
  sku_tier            = var.sku_tier

  # Private cluster configuration
  private_cluster_enabled             = var.private_cluster_enabled
  private_dns_zone_id                 = var.private_cluster_enabled ? var.private_dns_zone_id : null
  private_cluster_public_fqdn_enabled = false

  # OIDC and Workload Identity
  oidc_issuer_enabled       = true
  workload_identity_enabled = true

  # Auto-upgrade
  automatic_channel_upgrade = var.auto_upgrade_channel

  # Node OS channel upgrade
  node_os_channel_upgrade = "NodeImage"

  # Local account disabled (enforce AAD auth)
  local_account_disabled = true

  ###############################################################################
  # System Node Pool
  ###############################################################################

  default_node_pool {
    name                         = var.system_node_pool_name
    vm_size                      = var.system_node_pool_vm_size
    node_count                   = var.system_node_pool_node_count
    os_disk_size_gb              = var.system_node_pool_os_disk_size_gb
    os_disk_type                 = "Ephemeral"
    max_pods                     = var.system_node_pool_max_pods
    vnet_subnet_id               = var.vnet_subnet_id
    pod_subnet_id                = var.pod_subnet_id
    type                         = "VirtualMachineScaleSets"
    zones                        = var.system_node_pool_availability_zones
    only_critical_addons_enabled = true
    temporary_name_for_rotation  = "tmppool"

    node_labels = {
      "kubernetes.azure.com/mode" = "system"
      "workload-type"             = "system"
    }

    upgrade_settings {
      max_surge = "10%"
    }
  }

  ###############################################################################
  # Identity
  ###############################################################################

  identity {
    type         = var.identity_type
    identity_ids = var.identity_type == "UserAssigned" ? [local.control_plane_identity_id] : null
  }

  kubelet_identity {
    client_id                 = local.kubelet_client_id
    object_id                 = local.kubelet_object_id
    user_assigned_identity_id = local.kubelet_identity_id
  }

  ###############################################################################
  # Azure AD Integration
  ###############################################################################

  azure_active_directory_role_based_access_control {
    managed                = true
    admin_group_object_ids = var.admin_group_object_ids
    azure_rbac_enabled     = var.azure_rbac_enabled
    tenant_id              = data.azurerm_client_config.current.tenant_id
  }

  ###############################################################################
  # Network Profile
  ###############################################################################

  network_profile {
    network_plugin     = var.network_plugin
    network_policy     = var.network_policy
    outbound_type      = var.outbound_type
    service_cidr       = var.service_cidr
    dns_service_ip     = var.dns_service_ip
    load_balancer_sku  = "standard"

    load_balancer_profile {
      outbound_ports_allocated  = 0
      idle_timeout_in_minutes   = 30
      managed_outbound_ip_count = var.outbound_type == "loadBalancer" ? 1 : null
    }
  }

  ###############################################################################
  # Add-ons
  ###############################################################################

  azure_policy_enabled = var.azure_policy_enabled

  dynamic "oms_agent" {
    for_each = var.oms_agent_enabled && var.log_analytics_workspace_id != null ? [1] : []
    content {
      log_analytics_workspace_id      = var.log_analytics_workspace_id
      msi_auth_for_monitoring_enabled = true
    }
  }

  dynamic "key_vault_secrets_provider" {
    for_each = var.key_vault_secrets_provider_enabled ? [1] : []
    content {
      secret_rotation_enabled  = var.secret_rotation_enabled
      secret_rotation_interval = var.secret_rotation_interval
    }
  }

  ###############################################################################
  # Maintenance Window
  ###############################################################################

  maintenance_window {
    allowed {
      day   = var.maintenance_window_day
      hours = [var.maintenance_window_start_hour]
    }
  }

  ###############################################################################
  # Storage Profile
  ###############################################################################

  storage_profile {
    blob_driver_enabled         = true
    disk_driver_enabled         = true
    disk_driver_version         = "v1"
    file_driver_enabled         = true
    snapshot_controller_enabled = true
  }

  tags = merge(var.tags, { component = "aks" })

  lifecycle {
    ignore_changes = [
      # Kubernetes version is managed through auto-upgrade
      kubernetes_version,
      # Node count is managed through autoscaler
      default_node_pool[0].node_count,
    ]
  }

  depends_on = [
    azurerm_role_assignment.aks_network_contributor,
  ]
}

###############################################################################
# User Node Pool
###############################################################################

resource "azurerm_kubernetes_cluster_node_pool" "user" {
  name                  = var.user_node_pool_name
  kubernetes_cluster_id = azurerm_kubernetes_cluster.this.id
  vm_size               = var.user_node_pool_vm_size
  os_disk_size_gb       = var.user_node_pool_os_disk_size_gb
  os_disk_type          = "Managed"
  max_pods              = var.user_node_pool_max_pods
  vnet_subnet_id        = var.vnet_subnet_id
  pod_subnet_id         = var.pod_subnet_id
  zones                 = var.user_node_pool_availability_zones
  mode                  = "User"

  # Autoscaling
  enable_auto_scaling = true
  min_count           = var.user_node_pool_min_count
  max_count           = var.user_node_pool_max_count
  node_count          = var.user_node_pool_initial_count

  node_labels = var.user_node_pool_node_labels
  node_taints = var.user_node_pool_node_taints

  upgrade_settings {
    max_surge = "33%"
  }

  tags = merge(var.tags, { component = "aks-user-pool" })

  lifecycle {
    ignore_changes = [node_count]
  }
}

###############################################################################
# Data Sources
###############################################################################

data "azurerm_client_config" "current" {}

###############################################################################
# Diagnostic Settings
###############################################################################

resource "azurerm_monitor_diagnostic_setting" "aks" {
  count = var.log_analytics_workspace_id != null ? 1 : 0

  name                       = "diag-aks"
  target_resource_id         = azurerm_kubernetes_cluster.this.id
  log_analytics_workspace_id = var.log_analytics_workspace_id

  enabled_log {
    category = "kube-apiserver"
  }
  enabled_log {
    category = "kube-audit"
  }
  enabled_log {
    category = "kube-audit-admin"
  }
  enabled_log {
    category = "kube-controller-manager"
  }
  enabled_log {
    category = "kube-scheduler"
  }
  enabled_log {
    category = "cluster-autoscaler"
  }
  enabled_log {
    category = "guard"
  }

  metric {
    category = "AllMetrics"
    enabled  = true
  }
}
