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

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}

###############################################################################
# Locals
###############################################################################

locals {
  common_labels = merge(
    {
      project     = var.project_name
      environment = var.environment
      managed_by  = "terraform"
      repo        = "ai-agent-security-operations-center"
    },
    var.labels
  )
}

###############################################################################
# APIs to Enable
###############################################################################

locals {
  required_apis = [
    "container.googleapis.com",
    "containerregistry.googleapis.com",
    "artifactregistry.googleapis.com",
    "compute.googleapis.com",
    "iam.googleapis.com",
    "cloudkms.googleapis.com",
    "secretmanager.googleapis.com",
    "monitoring.googleapis.com",
    "logging.googleapis.com",
    "cloudtrace.googleapis.com",
    "dns.googleapis.com",
    "servicenetworking.googleapis.com",
    "binaryauthorization.googleapis.com",
    "pubsub.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "networkconnectivity.googleapis.com",
  ]
}

resource "google_project_service" "this" {
  for_each = toset(local.required_apis)

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

###############################################################################
# Network Module
###############################################################################

module "network" {
  source = "../../../gcp/network"

  project_id = var.project_id
  region     = var.region
  vpc_name   = var.vpc_name

  subnets = {
    gke_nodes = {
      region        = var.region
      ip_cidr_range = var.gke_nodes_cidr
      secondary_ranges = [
        {
          range_name    = "gke-pods"
          ip_cidr_range = var.gke_pods_cidr
        },
        {
          range_name    = "gke-services"
          ip_cidr_range = var.gke_services_cidr
        }
      ]
      log_config = {
        aggregation_interval = "INTERVAL_5_SEC"
        flow_sampling        = 0.5
        metadata             = "INCLUDE_ALL_METADATA"
      }
    }
    management = {
      region        = var.region
      ip_cidr_range = "10.4.0.0/24"
      secondary_ranges = []
    }
    private_services = {
      region        = var.region
      ip_cidr_range = "10.5.0.0/24"
      secondary_ranges = []
    }
  }

  enable_private_service_access = var.enable_private_service_access
  labels                        = local.common_labels

  depends_on = [google_project_service.this]
}

###############################################################################
# GKE Module
###############################################################################

module "gke" {
  source = "../../../gcp/gke"

  project_id = var.project_id
  region     = var.region
  cluster_name = var.cluster_name

  network    = module.network.vpc_name
  subnetwork = module.network.subnet_ids["gke_nodes"]

  pods_secondary_range_name     = module.network.gke_pods_secondary_range_name
  services_secondary_range_name = module.network.gke_services_secondary_range_name

  master_ipv4_cidr_block     = var.master_ipv4_cidr_block
  master_authorized_networks = var.master_authorized_networks

  # Security features
  enable_workload_identity             = true
  enable_binary_authorization          = var.enable_binary_authorization
  enable_shielded_nodes                = true
  enable_config_connector              = var.enable_config_connector
  enable_dataplane_v2                  = true

  # Private cluster
  private_cluster_enabled  = true
  enable_private_endpoint  = true

  release_channel    = var.release_channel
  deletion_protection = var.deletion_protection

  labels = local.common_labels

  depends_on = [module.network]
}

###############################################################################
# Artifact Registry
###############################################################################

resource "google_artifact_registry_repository" "this" {
  provider = google-beta

  project       = var.project_id
  location      = var.artifact_registry_location
  repository_id = "${var.project_name}-${var.environment}"
  description   = "Container images for ${var.project_name} ${var.environment}"
  format        = "DOCKER"

  docker_config {
    immutable_tags = false
  }

  cleanup_policies {
    id     = "keep-tagged-releases"
    action = "KEEP"
    condition {
      tag_state = "TAGGED"
    }
  }

  cleanup_policies {
    id     = "delete-old-untagged"
    action = "DELETE"
    condition {
      tag_state  = "UNTAGGED"
      older_than = "2592000s" # 30 days
    }
  }

  labels = local.common_labels

  depends_on = [google_project_service.this]
}

# Grant GKE workloads read access to the registry
resource "google_artifact_registry_repository_iam_member" "gke_reader" {
  project    = var.project_id
  location   = google_artifact_registry_repository.this.location
  repository = google_artifact_registry_repository.this.name
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${var.project_id}.svc.id.goog[default/default]"
}

###############################################################################
# Secret Manager
###############################################################################

resource "google_secret_manager_secret" "cluster_credentials" {
  project   = var.project_id
  secret_id = "gke-cluster-credentials-${var.environment}"

  labels = local.common_labels

  replication {
    auto {}
  }

  depends_on = [google_project_service.this]
}

###############################################################################
# Cloud Monitoring Alert Policies
###############################################################################

resource "google_monitoring_alert_policy" "gke_node_not_ready" {
  display_name = "${var.cluster_name}: Node Not Ready"
  project      = var.project_id
  combiner     = "OR"

  conditions {
    display_name = "GKE Node Not Ready"
    condition_threshold {
      filter          = "resource.type = \"k8s_node\" AND metric.type = \"kubernetes.io/node/ready\""
      duration        = "300s"
      comparison      = "COMPARISON_LT"
      threshold_value = 1

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  alert_strategy {
    auto_close = "1800s"
  }

  user_labels = local.common_labels
}

###############################################################################
# Binary Authorization Policy
###############################################################################

resource "google_binary_authorization_policy" "this" {
  count = var.enable_binary_authorization ? 1 : 0

  project = var.project_id

  admission_whitelist_patterns {
    name_pattern = "gcr.io/google_containers/*"
  }

  admission_whitelist_patterns {
    name_pattern = "${var.artifact_registry_location}-docker.pkg.dev/${var.project_id}/${var.project_name}-${var.environment}/*"
  }

  default_admission_rule {
    evaluation_mode  = "REQUIRE_ATTESTATION"
    enforcement_mode = "ENFORCED_BLOCK_AND_AUDIT_LOG"

    require_attestations_by = []
  }

  global_policy_evaluation_mode = "ENABLE"

  depends_on = [google_project_service.this]
}
