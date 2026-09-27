output "cluster_id" {
  description = "Resource ID of the AKS cluster"
  value       = azurerm_kubernetes_cluster.this.id
}

output "cluster_name" {
  description = "Name of the AKS cluster"
  value       = azurerm_kubernetes_cluster.this.name
}

output "cluster_fqdn" {
  description = "FQDN of the AKS cluster"
  value       = azurerm_kubernetes_cluster.this.fqdn
}

output "cluster_private_fqdn" {
  description = "Private FQDN of the AKS cluster (when private cluster is enabled)"
  value       = azurerm_kubernetes_cluster.this.private_fqdn
}

output "kube_config_raw" {
  description = "Raw kubeconfig for the AKS cluster"
  value       = azurerm_kubernetes_cluster.this.kube_config_raw
  sensitive   = true
}

output "kube_config" {
  description = "Kubeconfig attributes for the AKS cluster"
  value       = azurerm_kubernetes_cluster.this.kube_config
  sensitive   = true
}

output "kube_admin_config_raw" {
  description = "Raw admin kubeconfig for the AKS cluster"
  value       = azurerm_kubernetes_cluster.this.kube_admin_config_raw
  sensitive   = true
}

output "node_resource_group" {
  description = "Auto-generated resource group containing AKS node resources"
  value       = azurerm_kubernetes_cluster.this.node_resource_group
}

output "identity" {
  description = "The identity block for the AKS cluster"
  value       = azurerm_kubernetes_cluster.this.identity
}

output "kubelet_identity" {
  description = "The kubelet identity for the AKS cluster"
  value       = azurerm_kubernetes_cluster.this.kubelet_identity
}

output "oidc_issuer_url" {
  description = "OIDC issuer URL for the AKS cluster (used for Workload Identity)"
  value       = azurerm_kubernetes_cluster.this.oidc_issuer_url
}

output "control_plane_identity_id" {
  description = "Resource ID of the control plane user-assigned identity"
  value       = length(azurerm_user_assigned_identity.aks_control_plane) > 0 ? azurerm_user_assigned_identity.aks_control_plane[0].id : var.user_assigned_identity_id
}

output "control_plane_identity_principal_id" {
  description = "Principal ID (object ID) of the control plane identity"
  value       = length(azurerm_user_assigned_identity.aks_control_plane) > 0 ? azurerm_user_assigned_identity.aks_control_plane[0].principal_id : null
}

output "kubelet_identity_id" {
  description = "Resource ID of the kubelet user-assigned identity"
  value       = length(azurerm_user_assigned_identity.aks_kubelet) > 0 ? azurerm_user_assigned_identity.aks_kubelet[0].id : var.kubelet_identity_user_assigned_identity_id
}

output "kubelet_identity_client_id" {
  description = "Client ID of the kubelet identity"
  value       = length(azurerm_user_assigned_identity.aks_kubelet) > 0 ? azurerm_user_assigned_identity.aks_kubelet[0].client_id : var.kubelet_identity_client_id
}

output "kubelet_identity_object_id" {
  description = "Object ID of the kubelet identity"
  value       = length(azurerm_user_assigned_identity.aks_kubelet) > 0 ? azurerm_user_assigned_identity.aks_kubelet[0].principal_id : var.kubelet_identity_object_id
}

output "key_vault_secrets_provider_identity" {
  description = "Identity used by the Key Vault secrets provider"
  value       = azurerm_kubernetes_cluster.this.key_vault_secrets_provider
}

output "user_node_pool_id" {
  description = "Resource ID of the user node pool"
  value       = azurerm_kubernetes_cluster_node_pool.user.id
}
