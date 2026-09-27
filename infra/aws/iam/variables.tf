variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "ai-soc"
}

variable "environment" {
  description = "Deployment environment (prod, staging, dev)"
  type        = string
}

variable "oidc_provider_arn" {
  description = "ARN of the EKS OIDC provider for IRSA"
  type        = string
}

variable "oidc_provider_url" {
  description = "URL of the EKS OIDC provider"
  type        = string
}

variable "kms_key_arns" {
  description = "List of KMS key ARNs the roles should be allowed to use"
  type        = list(string)
  default     = []
}

variable "s3_bucket_arns" {
  description = "List of S3 bucket ARNs for policy statements"
  type        = list(string)
  default     = []
}

variable "model_artifacts_bucket_arns" {
  description = "ARNs of S3 buckets containing model artifacts (for Bedrock role)"
  type        = list(string)
  default     = []
}

variable "sqs_queue_arns" {
  description = "List of SQS queue ARNs for policy statements"
  type        = list(string)
  default     = []
}

variable "api_service_namespace" {
  description = "Kubernetes namespace for the API service"
  type        = string
  default     = "ai-soc"
}

variable "api_service_account_name" {
  description = "Kubernetes service account name for the API service"
  type        = string
  default     = "api-service"
}

variable "agent_namespace" {
  description = "Kubernetes namespace for agent workloads"
  type        = string
  default     = "ai-soc-agents"
}

variable "agent_service_account_name" {
  description = "Kubernetes service account name for agent workloads"
  type        = string
  default     = "agent-runtime"
}

variable "bedrock_service_account_name" {
  description = "Kubernetes service account name for Bedrock invocations"
  type        = string
  default     = "bedrock-invoker"
}

variable "enable_cloudtrail" {
  description = "Whether to create a CloudTrail for IAM audit logging"
  type        = bool
  default     = true
}

variable "audit_s3_bucket_name" {
  description = "S3 bucket name for CloudTrail logs"
  type        = string
  default     = ""
}
