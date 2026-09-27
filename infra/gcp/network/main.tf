terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.0"
    }
  }
}

###############################################################################
# VPC Network
###############################################################################

resource "google_compute_network" "this" {
  name                            = var.vpc_name
  project                         = var.project_id
  auto_create_subnetworks         = false
  routing_mode                    = "REGIONAL"
  delete_default_routes_on_create = true

  # Enable internal IPv6 (dual-stack)
  enable_ula_internal_ipv6 = false
}

###############################################################################
# Subnets
###############################################################################

resource "google_compute_subnetwork" "this" {
  for_each = var.subnets

  name          = each.key
  project       = var.project_id
  region        = each.value.region
  network       = google_compute_network.this.id
  ip_cidr_range = each.value.ip_cidr_range

  private_ip_google_access = each.value.private_ip_google_access

  dynamic "secondary_ip_range" {
    for_each = each.value.secondary_ranges
    content {
      range_name    = secondary_ip_range.value.range_name
      ip_cidr_range = secondary_ip_range.value.ip_cidr_range
    }
  }

  dynamic "log_config" {
    for_each = each.value.log_config != null ? [each.value.log_config] : []
    content {
      aggregation_interval = log_config.value.aggregation_interval
      flow_sampling        = log_config.value.flow_sampling
      metadata             = log_config.value.metadata
    }
  }
}

###############################################################################
# Cloud Router
###############################################################################

resource "google_compute_router" "this" {
  name    = "router-${var.vpc_name}"
  project = var.project_id
  region  = var.region
  network = google_compute_network.this.id

  bgp {
    asn            = 64514
    advertise_mode = "CUSTOM"
    advertised_groups = ["ALL_SUBNETS"]
  }
}

###############################################################################
# Cloud NAT
###############################################################################

resource "google_compute_router_nat" "this" {
  name                               = "nat-${var.vpc_name}"
  project                            = var.project_id
  router                             = google_compute_router.this.name
  region                             = google_compute_router.this.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "LIST_OF_SUBNETWORKS"

  dynamic "subnetwork" {
    for_each = google_compute_subnetwork.this
    content {
      name                    = subnetwork.value.id
      source_ip_ranges_to_nat = ["ALL_IP_RANGES"]
    }
  }

  min_ports_per_vm                    = var.cloud_nat_min_ports_per_vm
  enable_dynamic_port_allocation      = var.cloud_nat_enable_dynamic_port_allocation
  max_ports_per_vm                    = var.cloud_nat_enable_dynamic_port_allocation ? var.cloud_nat_max_ports_per_vm : null
  enable_endpoint_independent_mapping = false
  tcp_established_idle_timeout_sec    = 1200
  tcp_transitory_idle_timeout_sec     = 30
  udp_idle_timeout_sec                = 30

  log_config {
    enable = true
    filter = var.cloud_nat_log_filter
  }
}

###############################################################################
# Firewall Rules
###############################################################################

# Deny all ingress by default (GCP already does this, explicit for documentation)
resource "google_compute_firewall" "deny_all_ingress" {
  name        = "${var.vpc_name}-deny-all-ingress"
  project     = var.project_id
  network     = google_compute_network.this.id
  priority    = 65534
  direction   = "INGRESS"
  description = "Deny all ingress traffic - default deny rule"

  deny {
    protocol = "all"
  }

  source_ranges = ["0.0.0.0/0"]
}

# Allow Google health checks (required for load balancers)
resource "google_compute_firewall" "allow_health_checks" {
  name        = "${var.vpc_name}-allow-health-checks"
  project     = var.project_id
  network     = google_compute_network.this.id
  priority    = 1000
  direction   = "INGRESS"
  description = "Allow Google health check probes"

  allow {
    protocol = "tcp"
  }

  source_ranges = [
    "35.191.0.0/16",  # Google health checks
    "130.211.0.0/22", # Google health checks
  ]

  target_tags = ["allow-health-checks"]
}

# Allow internal VPC traffic
resource "google_compute_firewall" "allow_internal" {
  name        = "${var.vpc_name}-allow-internal"
  project     = var.project_id
  network     = google_compute_network.this.id
  priority    = 1000
  direction   = "INGRESS"
  description = "Allow internal VPC traffic"

  allow {
    protocol = "tcp"
  }

  allow {
    protocol = "udp"
  }

  allow {
    protocol = "icmp"
  }

  source_ranges = [for s in var.subnets : s.ip_cidr_range]
}

# Allow GKE master to nodes communication
resource "google_compute_firewall" "allow_gke_master_to_nodes" {
  name        = "${var.vpc_name}-allow-gke-master-nodes"
  project     = var.project_id
  network     = google_compute_network.this.id
  priority    = 1000
  direction   = "INGRESS"
  description = "Allow GKE control plane to node communication"

  allow {
    protocol = "tcp"
    ports    = ["443", "8443", "10250", "10255"]
  }

  source_ranges = ["172.16.0.0/28"] # GKE master CIDR (set per cluster)
  target_tags   = ["gke-node"]
}

# Egress - allow all (NAT handles routing)
resource "google_compute_firewall" "allow_all_egress" {
  name        = "${var.vpc_name}-allow-all-egress"
  project     = var.project_id
  network     = google_compute_network.this.id
  priority    = 1000
  direction   = "EGRESS"
  description = "Allow all egress traffic via Cloud NAT"

  allow {
    protocol = "all"
  }

  destination_ranges = ["0.0.0.0/0"]
}

# Default internet route via NAT
resource "google_compute_route" "default_internet_gateway" {
  name             = "${var.vpc_name}-default-internet"
  project          = var.project_id
  network          = google_compute_network.this.id
  dest_range       = "0.0.0.0/0"
  priority         = 1000
  next_hop_gateway = "default-internet-gateway"
  tags             = ["allow-internet-egress"]
}

###############################################################################
# Private Service Access (Cloud SQL, Memorystore, etc.)
###############################################################################

resource "google_compute_global_address" "private_service_access" {
  count = var.enable_private_service_access ? 1 : 0

  name          = "psa-${var.vpc_name}"
  project       = var.project_id
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.this.id
  address       = split("/", var.private_service_access_cidr)[0]
}

resource "google_service_networking_connection" "private_service_access" {
  count = var.enable_private_service_access ? 1 : 0

  network                 = google_compute_network.this.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_service_access[0].name]
}

###############################################################################
# Private Service Connect (for Google APIs)
###############################################################################

resource "google_compute_global_address" "psc_google_apis" {
  name         = "psc-google-apis"
  project      = var.project_id
  address_type = "INTERNAL"
  address      = var.private_service_connect_ip
  network      = google_compute_network.this.id
  purpose      = "PRIVATE_SERVICE_CONNECT"
}

resource "google_compute_global_forwarding_rule" "psc_google_apis" {
  name                  = "psc-google-apis"
  project               = var.project_id
  target                = "all-apis"
  network               = google_compute_network.this.id
  ip_address            = google_compute_global_address.psc_google_apis.id
  load_balancing_scheme = ""
}

# DNS policy for private Google APIs access
resource "google_dns_policy" "this" {
  name           = "dns-policy-${var.vpc_name}"
  project        = var.project_id
  enable_logging = true

  networks {
    network_url = google_compute_network.this.id
  }

  alternative_name_server_config {
    target_name_servers {
      ipv4_address    = "8.8.8.8"
      forwarding_path = "default"
    }
    target_name_servers {
      ipv4_address    = "8.8.4.4"
      forwarding_path = "default"
    }
  }
}
