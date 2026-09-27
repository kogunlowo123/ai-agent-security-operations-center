###############################################################################
# Resource Group Outputs
###############################################################################

output "resource_group_name" {
  description = "Name of the main resource group"
  value       = azurerm_resource_group.main.name
}

output "resource_group_id" {
  description = "Resource ID of the main resource group"
  value       = azurerm_resource_group.main.id
}

###############################################################################
# Network Outputs
###############################################################################

output "vnet_id" {
  description = "Resource ID of the virtual network"
  value       = module.network.vnet_id
}

output "vnet_name" {
  description = "Name of the virtual network"
  value       = module.network.vnet_name
}

output "subnet_ids" {
  description = "Map of subnet names to resource IDs"
  value       = module.network.subnet_ids
}

output "firewall_private_ip" {
  description = "Private IP of the Azure Firewall"
  value       = module.network.firewall_private_ip
}

###############################################################################
# AKS Outputs
###############################################################################

output "aks_cluster_id" {
  description = "Resource ID of the AKS cluster"
  value       = module.aks.cluster_id
}

output "aks_cluster_name" {
  description = "Name of the AKS cluster"
  value       = module.aks.cluster_name
}

output "aks_oidc_issuer_url" {
  description = "OIDC issuer URL for Workload Identity federation"
  value       = module.aks.oidc_issuer_url
}

output "aks_kube_config" {
  description = "Kubeconfig for the AKS cluster"
  value       = module.aks.kube_config_raw
  sensitive   = true
}

output "aks_node_resource_group" {
  description = "Auto-generated resource group for AKS node resources"
  value       = module.aks.node_resource_group
}

output "aks_kubelet_identity_object_id" {
  description = "Object ID of the AKS kubelet identity"
  value       = module.aks.kubelet_identity_object_id
}

output "aks_kubelet_identity_client_id" {
  description = "Client ID of the AKS kubelet identity"
  value       = module.aks.kubelet_identity_client_id
}

###############################################################################
# Container Registry Outputs
###############################################################################

output "acr_id" {
  description = "Resource ID of the Azure Container Registry"
  value       = azurerm_container_registry.this.id
}

output "acr_login_server" {
  description = "Login server URL of the Azure Container Registry"
  value       = azurerm_container_registry.this.login_server
}

###############################################################################
# Key Vault Outputs
###############################################################################

output "key_vault_id" {
  description = "Resource ID of the Key Vault"
  value       = azurerm_key_vault.this.id
}

output "key_vault_uri" {
  description = "URI of the Key Vault"
  value       = azurerm_key_vault.this.vault_uri
}

###############################################################################
# Monitoring Outputs
###############################################################################

output "log_analytics_workspace_id" {
  description = "Resource ID of the Log Analytics workspace"
  value       = azurerm_log_analytics_workspace.this.id
}

output "log_analytics_workspace_key" {
  description = "Primary key of the Log Analytics workspace"
  value       = azurerm_log_analytics_workspace.this.primary_shared_key
  sensitive   = true
}
