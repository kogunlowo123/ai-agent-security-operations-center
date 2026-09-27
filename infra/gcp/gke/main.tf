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
# Service Account for Config Connector
###############################################################################

resource "google_service_account" "config_connector" {
  count = var.enable_config_connector ? 1 : 0

  account_id   = "sa-${var.cluster_name}-cnfg-conn"
  display_name = "Config Connector SA for ${var.cluster_name}"
  project      = var.project_id
}

resource "google_project_iam_member" "config_connector_editor" {
  count = var.enable_config_connector ? 1 : 0

  project = var.project_id
  role    = "roles/editor"
  member  = "serviceAccount:${google_service_account.config_connector[0].email}"
}

# Allow Config Connector KSA to impersonate the GSA via Workload Identity
resource "google_service_account_iam_member" "config_connector_workload_identity" {
  count = var.enable_config_connector ? 1 : 0

  service_account_id = google_service_account.config_connector[0].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[cnrm-system/cnrm-controller-manager]"

  depends_on = [google_container_cluster.this]
}

###############################################################################
# GKE Autopilot Cluster
###############################################################################

resource "google_container_cluster" "this" {
  provider = google-beta

  name     = var.cluster_name
  project  = var.project_id
  location = var.region

  # Autopilot mode: fully managed node pools
  enable_autopilot = true

  # Networking
  network    = var.network
  subnetwork = var.subnetwork

  ip_allocation_policy {
    cluster_secondary_range_name  = var.pods_secondary_range_name
    services_secondary_range_name = var.services_secondary_range_name
  }

  # Private cluster
  private_cluster_config {
    enable_private_nodes    = var.private_cluster_enabled
    enable_private_endpoint = var.enable_private_endpoint
    master_ipv4_cidr_block  = var.master_ipv4_cidr_block

    master_global_access_config {
      enabled = !var.enable_private_endpoint
    }
  }

  # Master authorized networks
  master_authorized_networks_config {
    dynamic "cidr_blocks" {
      for_each = var.master_authorized_networks
      content {
        cidr_block   = cidr_blocks.value.cidr_block
        display_name = cidr_blocks.value.display_name
      }
    }
  }

  # Workload Identity
  dynamic "workload_identity_config" {
    for_each = var.enable_workload_identity ? [1] : []
    content {
      workload_pool = "${var.project_id}.svc.id.goog"
    }
  }

  # Binary Authorization
  binary_authorization {
    evaluation_mode = var.enable_binary_authorization ? var.binary_authorization_evaluation_mode : "DISABLED"
  }

  # Release channel
  release_channel {
    channel = var.release_channel
  }

  # Add-ons
  addons_config {
    http_load_balancing {
      disabled = !var.enable_http_load_balancing
    }

    horizontal_pod_autoscaling {
      disabled = !var.enable_horizontal_pod_autoscaling
    }

    dns_cache_config {
      enabled = var.enable_dns_cache
    }

    gce_persistent_disk_csi_driver_config {
      enabled = var.enable_gce_persistent_disk_csi_driver
    }

    dynamic "gcs_fuse_csi_driver_config" {
      for_each = var.enable_gcs_fuse_csi_driver ? [1] : []
      content {
        enabled = true
      }
    }

    dynamic "config_connector_config" {
      for_each = var.enable_config_connector ? [1] : []
      content {
        enabled = true
      }
    }
  }

  # Dataplane V2 (eBPF / Cilium)
  datapath_provider = var.enable_dataplane_v2 ? "ADVANCED_DATAPATH" : "LEGACY_DATAPATH"

  # Network policy (only with standard dataplane)
  dynamic "network_policy" {
    for_each = var.enable_network_policy && !var.enable_dataplane_v2 ? [1] : []
    content {
      enabled  = true
      provider = "CALICO"
    }
  }

  # Logging
  logging_config {
    enable_components = var.log_config_components
  }

  # Monitoring
  monitoring_config {
    enable_components = var.monitoring_components

    managed_prometheus {
      enabled = true
    }

    advanced_datapath_observability_config {
      enable_metrics = true
      relay_mode     = "INTERNAL_VPC_LB"
    }
  }

  # Maintenance window
  maintenance_policy {
    recurring_window {
      start_time = var.maintenance_start_time
      end_time   = var.maintenance_end_time
      recurrence = var.maintenance_recurrence
    }
  }

  # Security configuration
  master_auth {
    # Disable client certificate authentication
    client_certificate_config {
      issue_client_certificate = false
    }
  }

  # Shielded nodes are configured at node pool level in standard, but in
  # Autopilot they apply to all nodes by default. Explicitly set for clarity.
  node_config {
    shielded_instance_config {
      enable_secure_boot          = var.enable_shielded_nodes
      enable_integrity_monitoring = var.enable_shielded_nodes
    }

    workload_metadata_config {
      mode = "GKE_METADATA"
    }
  }

  # Cluster security posture
  security_posture_config {
    mode               = "BASIC"
    vulnerability_mode = "VULNERABILITY_ENTERPRISE"
  }

  # Enable secret encryption at rest
  database_encryption {
    state    = "ENCRYPTED"
    key_name = google_kms_crypto_key.cluster_secrets.id
  }

  notification_config {
    pubsub {
      enabled = true
      topic   = google_pubsub_topic.cluster_notifications.id
    }
  }

  resource_labels = var.labels

  deletion_protection = var.deletion_protection

  depends_on = [
    google_kms_crypto_key_iam_member.gke_kms,
  ]
}

###############################################################################
# KMS Key Ring & Crypto Key for Secret Encryption
###############################################################################

resource "google_kms_key_ring" "this" {
  name     = "kr-${var.cluster_name}"
  location = var.region
  project  = var.project_id
}

resource "google_kms_crypto_key" "cluster_secrets" {
  name            = "ck-${var.cluster_name}-secrets"
  key_ring        = google_kms_key_ring.this.id
  rotation_period = "7776000s" # 90 days

  lifecycle {
    prevent_destroy = true
  }

  version_template {
    algorithm        = "GOOGLE_SYMMETRIC_ENCRYPTION"
    protection_level = "SOFTWARE"
  }
}

# Grant GKE service account access to KMS key
resource "google_kms_crypto_key_iam_member" "gke_kms" {
  crypto_key_id = google_kms_crypto_key.cluster_secrets.id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = "serviceAccount:service-${data.google_project.this.number}@container-engine-robot.iam.gserviceaccount.com"
}

###############################################################################
# Pub/Sub Topic for Cluster Notifications
###############################################################################

resource "google_pubsub_topic" "cluster_notifications" {
  name    = "topic-${var.cluster_name}-notifications"
  project = var.project_id

  labels = var.labels
}

###############################################################################
# Data Sources
###############################################################################

data "google_project" "this" {
  project_id = var.project_id
}

data "google_container_cluster" "this" {
  name     = google_container_cluster.this.name
  location = google_container_cluster.this.location
  project  = var.project_id

  depends_on = [google_container_cluster.this]
}
