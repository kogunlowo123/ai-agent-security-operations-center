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
# Virtual Network
###############################################################################

resource "azurerm_virtual_network" "this" {
  name                = var.vnet_name
  location            = var.location
  resource_group_name = var.resource_group_name
  address_space       = var.vnet_address_space
  dns_servers         = var.dns_servers

  dynamic "ddos_protection_plan" {
    for_each = var.enable_ddos_protection ? [1] : []
    content {
      id     = var.ddos_protection_plan_id
      enable = true
    }
  }

  tags = merge(var.tags, { component = "network" })
}

###############################################################################
# Subnets
###############################################################################

resource "azurerm_subnet" "this" {
  for_each = var.subnets

  name                 = each.key
  resource_group_name  = var.resource_group_name
  virtual_network_name = azurerm_virtual_network.this.name
  address_prefixes     = [each.value.address_prefix]
  service_endpoints    = each.value.service_endpoints

  dynamic "delegation" {
    for_each = each.value.delegations
    content {
      name = delegation.value.name
      service_delegation {
        name    = delegation.value.name
        actions = delegation.value.actions
      }
    }
  }
}

###############################################################################
# Network Security Groups
###############################################################################

resource "azurerm_network_security_group" "aks_nodes" {
  name                = "nsg-aks-nodes"
  location            = var.location
  resource_group_name = var.resource_group_name
  tags                = merge(var.tags, { component = "nsg" })
}

resource "azurerm_network_security_rule" "aks_nodes_allow_inbound_azure_lb" {
  name                        = "AllowInboundAzureLoadBalancer"
  priority                    = 100
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "*"
  source_port_range           = "*"
  destination_port_range      = "*"
  source_address_prefix       = "AzureLoadBalancer"
  destination_address_prefix  = "*"
  resource_group_name         = var.resource_group_name
  network_security_group_name = azurerm_network_security_group.aks_nodes.name
}

resource "azurerm_network_security_rule" "aks_nodes_allow_inbound_vnet" {
  name                        = "AllowInboundVNet"
  priority                    = 110
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "*"
  source_port_range           = "*"
  destination_port_range      = "*"
  source_address_prefix       = "VirtualNetwork"
  destination_address_prefix  = "VirtualNetwork"
  resource_group_name         = var.resource_group_name
  network_security_group_name = azurerm_network_security_group.aks_nodes.name
}

resource "azurerm_network_security_rule" "aks_nodes_deny_all_inbound" {
  name                        = "DenyAllInbound"
  priority                    = 4000
  direction                   = "Inbound"
  access                      = "Deny"
  protocol                    = "*"
  source_port_range           = "*"
  destination_port_range      = "*"
  source_address_prefix       = "*"
  destination_address_prefix  = "*"
  resource_group_name         = var.resource_group_name
  network_security_group_name = azurerm_network_security_group.aks_nodes.name
}

resource "azurerm_network_security_rule" "aks_nodes_allow_outbound_internet" {
  name                        = "AllowOutboundInternet"
  priority                    = 100
  direction                   = "Outbound"
  access                      = "Allow"
  protocol                    = "*"
  source_port_range           = "*"
  destination_port_range      = "*"
  source_address_prefix       = "*"
  destination_address_prefix  = "Internet"
  resource_group_name         = var.resource_group_name
  network_security_group_name = azurerm_network_security_group.aks_nodes.name
}

resource "azurerm_network_security_group" "management" {
  name                = "nsg-management"
  location            = var.location
  resource_group_name = var.resource_group_name
  tags                = merge(var.tags, { component = "nsg" })
}

resource "azurerm_network_security_rule" "mgmt_allow_ssh_from_bastion" {
  name                        = "AllowSSHFromBastion"
  priority                    = 100
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "22"
  source_address_prefix       = var.subnets["azure_bastion"].address_prefix
  destination_address_prefix  = "*"
  resource_group_name         = var.resource_group_name
  network_security_group_name = azurerm_network_security_group.management.name
}

###############################################################################
# NSG Associations
###############################################################################

resource "azurerm_subnet_network_security_group_association" "aks_nodes" {
  subnet_id                 = azurerm_subnet.this["aks_nodes"].id
  network_security_group_id = azurerm_network_security_group.aks_nodes.id
}

resource "azurerm_subnet_network_security_group_association" "management" {
  subnet_id                 = azurerm_subnet.this["management"].id
  network_security_group_id = azurerm_network_security_group.management.id
}

###############################################################################
# Azure Firewall Public IP
###############################################################################

resource "azurerm_public_ip" "firewall" {
  name                = "pip-ai-soc-firewall"
  location            = var.location
  resource_group_name = var.resource_group_name
  allocation_method   = "Static"
  sku                 = "Standard"
  zones               = ["1", "2", "3"]
  tags                = merge(var.tags, { component = "firewall" })
}

resource "azurerm_public_ip" "firewall_management" {
  name                = "pip-ai-soc-firewall-mgmt"
  location            = var.location
  resource_group_name = var.resource_group_name
  allocation_method   = "Static"
  sku                 = "Standard"
  zones               = ["1", "2", "3"]
  tags                = merge(var.tags, { component = "firewall" })
}

###############################################################################
# Azure Firewall Policy
###############################################################################

resource "azurerm_firewall_policy" "this" {
  name                     = "afwp-ai-soc"
  resource_group_name      = var.resource_group_name
  location                 = var.location
  sku                      = var.firewall_sku_tier
  threat_intelligence_mode = "Alert"

  insights {
    enabled                            = var.log_analytics_workspace_id != null
    default_log_analytics_workspace_id = var.log_analytics_workspace_id
    retention_in_days                  = 30
  }

  intrusion_detection {
    mode = "Alert"
  }

  dns {
    proxy_enabled = true
  }

  tags = merge(var.tags, { component = "firewall" })
}

resource "azurerm_firewall_policy_rule_collection_group" "aks" {
  name               = "aks-rule-collection-group"
  firewall_policy_id = azurerm_firewall_policy.this.id
  priority           = 100

  application_rule_collection {
    name     = "aks-required-outbound"
    priority = 100
    action   = "Allow"

    rule {
      name = "allow-aks-api-server"
      protocols {
        type = "Https"
        port = 443
      }
      source_addresses  = [var.subnets["aks_nodes"].address_prefix]
      destination_fqdns = ["*.hcp.${var.location}.azmk8s.io"]
    }

    rule {
      name = "allow-microsoft-container-registry"
      protocols {
        type = "Https"
        port = 443
      }
      source_addresses       = [var.subnets["aks_nodes"].address_prefix]
      destination_fqdn_tags  = ["MicrosoftContainerRegistry"]
    }

    rule {
      name = "allow-azure-monitor"
      protocols {
        type = "Https"
        port = 443
      }
      source_addresses       = [var.subnets["aks_nodes"].address_prefix]
      destination_fqdn_tags  = ["AzureMonitor"]
    }

    rule {
      name = "allow-azure-active-directory"
      protocols {
        type = "Https"
        port = 443
      }
      source_addresses       = [var.subnets["aks_nodes"].address_prefix]
      destination_fqdn_tags  = ["AzureActiveDirectory"]
    }
  }

  network_rule_collection {
    name     = "aks-required-network"
    priority = 200
    action   = "Allow"

    rule {
      name                  = "allow-aks-udp-1194"
      protocols             = ["UDP"]
      source_addresses      = [var.subnets["aks_nodes"].address_prefix]
      destination_addresses = ["AzureCloud.${var.location}"]
      destination_ports     = ["1194"]
    }

    rule {
      name                  = "allow-aks-tcp-9000"
      protocols             = ["TCP"]
      source_addresses      = [var.subnets["aks_nodes"].address_prefix]
      destination_addresses = ["AzureCloud.${var.location}"]
      destination_ports     = ["9000"]
    }

    rule {
      name                  = "allow-ntp"
      protocols             = ["UDP"]
      source_addresses      = [var.subnets["aks_nodes"].address_prefix]
      destination_addresses = ["*"]
      destination_ports     = ["123"]
    }
  }
}

###############################################################################
# Azure Firewall
###############################################################################

resource "azurerm_firewall" "this" {
  name                = "afw-ai-soc"
  location            = var.location
  resource_group_name = var.resource_group_name
  sku_name            = "AZFW_VNet"
  sku_tier            = var.firewall_sku_tier
  firewall_policy_id  = azurerm_firewall_policy.this.id
  zones               = ["1", "2", "3"]

  ip_configuration {
    name                 = "primary"
    subnet_id            = azurerm_subnet.this["azure_firewall"].id
    public_ip_address_id = azurerm_public_ip.firewall.id
  }

  management_ip_configuration {
    name                 = "management"
    subnet_id            = azurerm_subnet.this["azure_firewall"].id
    public_ip_address_id = azurerm_public_ip.firewall_management.id
  }

  tags = merge(var.tags, { component = "firewall" })

  depends_on = [azurerm_firewall_policy_rule_collection_group.aks]
}

###############################################################################
# Route Table (force-tunnel via Firewall)
###############################################################################

resource "azurerm_route_table" "aks" {
  name                          = "rt-aks-nodes"
  location                      = var.location
  resource_group_name           = var.resource_group_name
  disable_bgp_route_propagation = true
  tags                          = merge(var.tags, { component = "routing" })
}

resource "azurerm_route" "aks_default_via_firewall" {
  name                   = "default-via-firewall"
  resource_group_name    = var.resource_group_name
  route_table_name       = azurerm_route_table.aks.name
  address_prefix         = "0.0.0.0/0"
  next_hop_type          = "VirtualAppliance"
  next_hop_in_ip_address = azurerm_firewall.this.ip_configuration[0].private_ip_address
}

resource "azurerm_subnet_route_table_association" "aks_nodes" {
  subnet_id      = azurerm_subnet.this["aks_nodes"].id
  route_table_id = azurerm_route_table.aks.id
}

###############################################################################
# Diagnostic Settings
###############################################################################

resource "azurerm_monitor_diagnostic_setting" "firewall" {
  count = var.log_analytics_workspace_id != null ? 1 : 0

  name                       = "diag-firewall"
  target_resource_id         = azurerm_firewall.this.id
  log_analytics_workspace_id = var.log_analytics_workspace_id

  enabled_log {
    category = "AzureFirewallApplicationRule"
  }
  enabled_log {
    category = "AzureFirewallNetworkRule"
  }
  enabled_log {
    category = "AzureFirewallDnsProxy"
  }
  enabled_log {
    category = "AzureFirewallThreatIntel"
  }

  metric {
    category = "AllMetrics"
    enabled  = true
  }
}
