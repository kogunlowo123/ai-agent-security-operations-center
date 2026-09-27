output "vnet_id" {
  description = "The resource ID of the virtual network"
  value       = azurerm_virtual_network.this.id
}

output "vnet_name" {
  description = "The name of the virtual network"
  value       = azurerm_virtual_network.this.name
}

output "vnet_address_space" {
  description = "The address space of the virtual network"
  value       = azurerm_virtual_network.this.address_space
}

output "subnet_ids" {
  description = "Map of subnet names to their resource IDs"
  value       = { for k, v in azurerm_subnet.this : k => v.id }
}

output "subnet_address_prefixes" {
  description = "Map of subnet names to their address prefixes"
  value       = { for k, v in azurerm_subnet.this : k => v.address_prefixes[0] }
}

output "nsg_aks_nodes_id" {
  description = "Resource ID of the AKS nodes network security group"
  value       = azurerm_network_security_group.aks_nodes.id
}

output "nsg_management_id" {
  description = "Resource ID of the management network security group"
  value       = azurerm_network_security_group.management.id
}

output "firewall_id" {
  description = "Resource ID of the Azure Firewall"
  value       = azurerm_firewall.this.id
}

output "firewall_private_ip" {
  description = "Private IP address of the Azure Firewall"
  value       = azurerm_firewall.this.ip_configuration[0].private_ip_address
}

output "firewall_public_ip" {
  description = "Public IP address of the Azure Firewall"
  value       = azurerm_public_ip.firewall.ip_address
}

output "firewall_policy_id" {
  description = "Resource ID of the Azure Firewall Policy"
  value       = azurerm_firewall_policy.this.id
}

output "route_table_aks_id" {
  description = "Resource ID of the AKS route table"
  value       = azurerm_route_table.aks.id
}
