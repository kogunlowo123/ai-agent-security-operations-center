terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.12"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.25"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Environment = var.environment
      Project     = var.project_name
      ManagedBy   = "terraform"
      Owner       = "security-ops"
      CostCenter  = "ai-soc-${var.environment}"
    }
  }
}

provider "helm" {
  kubernetes {
    host                   = module.eks.cluster_endpoint
    cluster_ca_certificate = base64decode(module.eks.cluster_ca)
    exec {
      api_version = "client.authentication.k8s.io/v1beta1"
      args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
      command     = "aws"
    }
  }
}

provider "kubernetes" {
  host                   = module.eks.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks.cluster_ca)
  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
    command     = "aws"
  }
}

locals {
  alarm_sns_topic_arns = var.alarm_sns_topic_arn != "" ? [var.alarm_sns_topic_arn] : []

  # Prod-specific settings
  single_nat_gateway = false  # HA: one NAT per AZ
  aurora_instances   = 3      # 1 writer + 2 readers
}

# ============================================================
# KMS Keys (created first, used by all other modules)
# ============================================================
module "kms" {
  source = "../../../aws/kms"

  project_name             = var.project_name
  environment              = var.environment
  authorized_iam_role_arns = var.authorized_iam_role_arns
  key_deletion_window_days = 30
  enable_multi_region_keys = false
  alarm_sns_topic_arns     = local.alarm_sns_topic_arns
}

# ============================================================
# Network
# ============================================================
module "network" {
  source = "../../../aws/network"

  project_name            = var.project_name
  environment             = var.environment
  aws_region              = var.aws_region
  vpc_cidr                = var.vpc_cidr
  enable_nat_gateway      = true
  single_nat_gateway      = local.single_nat_gateway
  flow_log_retention_days = 90
}

# ============================================================
# EKS
# ============================================================
module "eks" {
  source = "../../../aws/eks"

  project_name               = var.project_name
  environment                = var.environment
  aws_region                 = var.aws_region
  vpc_id                     = module.network.vpc_id
  private_subnet_ids         = module.network.private_subnet_ids
  kubernetes_version         = var.kubernetes_version
  kms_key_arn                = module.kms.eks_key_arn
  cluster_endpoint_public_access = false
  log_retention_days         = 90

  # System nodes: on-demand, HA across 3 AZs
  system_node_instance_types  = ["m5.large", "m5a.large", "m5d.large"]
  system_node_desired_size    = 3
  system_node_max_size        = 6
  system_node_min_size        = 3

  # Compute nodes: spot for cost efficiency
  compute_node_instance_types = ["m5.xlarge", "m5a.xlarge", "m5d.xlarge", "m4.xlarge", "m5n.xlarge"]
  compute_node_desired_size   = 2
  compute_node_max_size       = 20
  compute_node_min_size       = 0

  depends_on = [module.network, module.kms]
}

# ============================================================
# Aurora PostgreSQL with pgvector
# ============================================================
module "aurora_pgvector" {
  source = "../../../aws/aurora-pgvector"

  project_name               = var.project_name
  environment                = var.environment
  vpc_id                     = module.network.vpc_id
  private_subnet_ids         = module.network.private_subnet_ids
  kms_key_arn                = module.kms.database_key_arn
  allowed_security_group_ids = [module.eks.cluster_security_group_id]
  allowed_cidr_blocks        = [var.vpc_cidr]

  db_name            = "aisoc"
  db_master_username = "aisocadmin"
  engine_version     = "15.4"
  instance_class     = "db.r6g.large"
  instance_count     = local.aurora_instances

  backup_retention_period      = 14
  preferred_backup_window      = "03:00-04:00"
  preferred_maintenance_window = "sun:04:00-sun:05:00"
  deletion_protection          = true

  serverless_min_capacity = 0.5
  serverless_max_capacity = 16

  alarm_sns_topic_arns = local.alarm_sns_topic_arns

  depends_on = [module.network, module.kms]
}

# ============================================================
# OpenSearch
# ============================================================
module "opensearch" {
  source = "../../../aws/opensearch"

  project_name               = var.project_name
  environment                = var.environment
  vpc_id                     = module.network.vpc_id
  private_subnet_ids         = module.network.private_subnet_ids
  kms_key_arn                = module.kms.database_key_arn
  allowed_security_group_ids = [module.eks.cluster_security_group_id]
  allowed_cidr_blocks        = [var.vpc_cidr]
  allowed_iam_role_arns      = [module.iam.agent_runtime_role_arn]

  engine_version       = "2.11"
  data_instance_type   = "r6g.large.search"
  data_instance_count  = 3

  dedicated_master_enabled = true
  dedicated_master_type    = "r6g.large.search"
  dedicated_master_count   = 3

  warm_enabled = false

  ebs_volume_size = 100
  ebs_iops        = 3000
  ebs_throughput  = 125

  master_user                = "aisocadmin"
  create_service_linked_role = true
  log_retention_days         = 90

  alarm_sns_topic_arns = local.alarm_sns_topic_arns

  depends_on = [module.network, module.kms]
}

# ============================================================
# S3 Buckets
# ============================================================
module "s3" {
  source = "../../../aws/s3"

  project_name          = var.project_name
  environment           = var.environment
  kms_key_arn           = module.kms.s3_key_arn
  enable_access_logging = true

  # Wire threat intel bucket to triage SQS queue for event-driven processing
  threat_intel_event_queue_arn = module.sqs.triage_queue_arn

  depends_on = [module.kms, module.sqs]
}

# ============================================================
# SQS Queues
# ============================================================
module "sqs" {
  source = "../../../aws/sqs"

  project_name              = var.project_name
  environment               = var.environment
  kms_key_arn               = module.kms.sqs_key_arn
  message_retention_seconds = 345600  # 4 days

  triage_visibility_timeout           = 300
  hunt_visibility_timeout             = 900
  incident_visibility_timeout         = 600
  triage_queue_depth_alarm_threshold  = 1000

  allowed_sender_role_arns = [
    module.iam.api_service_role_arn,
    module.iam.agent_runtime_role_arn
  ]

  alarm_sns_topic_arns = local.alarm_sns_topic_arns

  depends_on = [module.kms]
}

# ============================================================
# IAM Roles
# ============================================================
module "iam" {
  source = "../../../aws/iam"

  project_name  = var.project_name
  environment   = var.environment

  oidc_provider_arn = module.eks.oidc_provider_arn
  oidc_provider_url = module.eks.oidc_provider_url

  kms_key_arns = [
    module.kms.database_key_arn,
    module.kms.s3_key_arn,
    module.kms.secrets_key_arn,
    module.kms.sqs_key_arn
  ]

  s3_bucket_arns = module.s3.all_bucket_arns

  model_artifacts_bucket_arns = [module.s3.model_artifacts_bucket_arn]

  sqs_queue_arns = module.sqs.all_queue_arns

  api_service_namespace    = "ai-soc"
  api_service_account_name = "api-service"

  agent_namespace              = "ai-soc-agents"
  agent_service_account_name   = "agent-runtime"
  bedrock_service_account_name = "bedrock-invoker"

  enable_cloudtrail    = true
  audit_s3_bucket_name = module.s3.audit_logs_bucket_name

  depends_on = [module.eks, module.kms, module.s3, module.sqs]
}

# ============================================================
# Bootstrap: Terraform state bucket and lock table
# (Run once before first apply with local backend)
# ============================================================
resource "aws_s3_bucket" "terraform_state" {
  bucket = "ai-soc-terraform-state-${var.environment}"

  tags = {
    Name        = "ai-soc-terraform-state-${var.environment}"
    Environment = var.environment
    Project     = var.project_name
    ManagedBy   = "terraform"
    Purpose     = "Terraform remote state"
  }
}

resource "aws_s3_bucket_versioning" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = module.kms.s3_key_arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "terraform_state" {
  bucket                  = aws_s3_bucket.terraform_state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "terraform_state_https_only" {
  bucket = aws_s3_bucket.terraform_state.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyNonHTTPS"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource = [
        aws_s3_bucket.terraform_state.arn,
        "${aws_s3_bucket.terraform_state.arn}/*"
      ]
      Condition = {
        Bool = {
          "aws:SecureTransport" = "false"
        }
      }
    }]
  })
}

resource "aws_dynamodb_table" "terraform_locks" {
  name         = "ai-soc-terraform-locks-${var.environment}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = module.kms.database_key_arn
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Name        = "ai-soc-terraform-locks-${var.environment}"
    Environment = var.environment
    Project     = var.project_name
    ManagedBy   = "terraform"
    Purpose     = "Terraform state locking"
  }
}
