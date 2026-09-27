# ============================================================
# Network outputs
# ============================================================
output "vpc_id" {
  description = "VPC ID"
  value       = module.network.vpc_id
}

output "public_subnet_ids" {
  description = "Public subnet IDs"
  value       = module.network.public_subnet_ids
}

output "private_subnet_ids" {
  description = "Private subnet IDs"
  value       = module.network.private_subnet_ids
}

output "availability_zones" {
  description = "Availability Zones used"
  value       = module.network.availability_zones
}

# ============================================================
# EKS outputs
# ============================================================
output "cluster_name" {
  description = "EKS cluster name"
  value       = module.eks.cluster_name
}

output "cluster_endpoint" {
  description = "EKS API server endpoint"
  value       = module.eks.cluster_endpoint
  sensitive   = true
}

output "cluster_ca" {
  description = "EKS cluster certificate authority data"
  value       = module.eks.cluster_ca
  sensitive   = true
}

output "oidc_provider_arn" {
  description = "OIDC provider ARN for IRSA"
  value       = module.eks.oidc_provider_arn
}

output "karpenter_role_arn" {
  description = "Karpenter IAM role ARN"
  value       = module.eks.karpenter_role_arn
}

output "alb_controller_role_arn" {
  description = "ALB controller IAM role ARN"
  value       = module.eks.alb_controller_role_arn
}

# ============================================================
# Database outputs
# ============================================================
output "aurora_endpoint" {
  description = "Aurora PostgreSQL writer endpoint"
  value       = module.aurora_pgvector.endpoint
  sensitive   = true
}

output "aurora_reader_endpoint" {
  description = "Aurora PostgreSQL reader endpoint"
  value       = module.aurora_pgvector.reader_endpoint
  sensitive   = true
}

output "aurora_port" {
  description = "Aurora PostgreSQL port"
  value       = module.aurora_pgvector.port
}

output "aurora_db_name" {
  description = "Aurora database name"
  value       = module.aurora_pgvector.db_name
}

output "aurora_secret_arn" {
  description = "Secrets Manager ARN for Aurora credentials"
  value       = module.aurora_pgvector.secret_arn
}

# ============================================================
# OpenSearch outputs
# ============================================================
output "opensearch_endpoint" {
  description = "OpenSearch domain endpoint"
  value       = module.opensearch.endpoint
  sensitive   = true
}

output "opensearch_domain_name" {
  description = "OpenSearch domain name"
  value       = module.opensearch.domain_name
}

output "opensearch_credentials_secret_arn" {
  description = "Secrets Manager ARN for OpenSearch credentials"
  value       = module.opensearch.credentials_secret_arn
}

# ============================================================
# S3 outputs
# ============================================================
output "threat_intel_bucket" {
  description = "Threat intelligence S3 bucket name"
  value       = module.s3.threat_intel_bucket_name
}

output "incident_artifacts_bucket" {
  description = "Incident artifacts S3 bucket name"
  value       = module.s3.incident_artifacts_bucket_name
}

output "model_artifacts_bucket" {
  description = "Model artifacts S3 bucket name"
  value       = module.s3.model_artifacts_bucket_name
}

# ============================================================
# SQS outputs
# ============================================================
output "triage_queue_url" {
  description = "Triage SQS queue URL"
  value       = module.sqs.triage_queue_url
}

output "hunt_queue_url" {
  description = "Hunt SQS queue URL"
  value       = module.sqs.hunt_queue_url
}

output "incident_queue_url" {
  description = "Incident SQS queue URL"
  value       = module.sqs.incident_queue_url
}

# ============================================================
# KMS outputs
# ============================================================
output "kms_key_arns" {
  description = "All KMS key ARNs by purpose"
  value       = module.kms.all_key_arns
  sensitive   = true
}

# ============================================================
# IAM outputs
# ============================================================
output "api_service_role_arn" {
  description = "API service IAM role ARN"
  value       = module.iam.api_service_role_arn
}

output "agent_runtime_role_arn" {
  description = "Agent runtime IAM role ARN"
  value       = module.iam.agent_runtime_role_arn
}

output "bedrock_invoke_role_arn" {
  description = "Bedrock invoke IAM role ARN"
  value       = module.iam.bedrock_invoke_role_arn
}

# ============================================================
# Terraform state infrastructure
# ============================================================
output "terraform_state_bucket" {
  description = "S3 bucket for Terraform remote state"
  value       = aws_s3_bucket.terraform_state.bucket
}

output "terraform_locks_table" {
  description = "DynamoDB table for Terraform state locking"
  value       = aws_dynamodb_table.terraform_locks.name
}
