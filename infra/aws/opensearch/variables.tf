variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "ai-soc"
}

variable "environment" {
  description = "Deployment environment (prod, staging, dev)"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID where OpenSearch will be deployed"
  type        = string
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs (at least 3 for multi-AZ)"
  type        = list(string)
}

variable "kms_key_arn" {
  description = "ARN of the KMS key for OpenSearch encryption"
  type        = string
}

variable "allowed_security_group_ids" {
  description = "Security group IDs allowed to connect to OpenSearch"
  type        = list(string)
  default     = []
}

variable "allowed_cidr_blocks" {
  description = "CIDR blocks allowed to access OpenSearch"
  type        = list(string)
  default     = []
}

variable "allowed_iam_role_arns" {
  description = "IAM role ARNs allowed to access OpenSearch"
  type        = list(string)
  default     = []
}

variable "engine_version" {
  description = "OpenSearch engine version"
  type        = string
  default     = "2.11"
}

variable "data_instance_type" {
  description = "Instance type for OpenSearch data nodes"
  type        = string
  default     = "r6g.large.search"
}

variable "data_instance_count" {
  description = "Number of data nodes in the OpenSearch domain"
  type        = number
  default     = 3
}

variable "dedicated_master_enabled" {
  description = "Whether to enable dedicated master nodes"
  type        = bool
  default     = true
}

variable "dedicated_master_type" {
  description = "Instance type for dedicated master nodes"
  type        = string
  default     = "r6g.large.search"
}

variable "dedicated_master_count" {
  description = "Number of dedicated master nodes"
  type        = number
  default     = 3
}

variable "warm_enabled" {
  description = "Whether to enable UltraWarm storage"
  type        = bool
  default     = false
}

variable "warm_count" {
  description = "Number of UltraWarm nodes"
  type        = number
  default     = 2
}

variable "warm_type" {
  description = "Instance type for UltraWarm nodes"
  type        = string
  default     = "ultrawarm1.medium.search"
}

variable "ebs_volume_size" {
  description = "EBS volume size per data node (GB)"
  type        = number
  default     = 100
}

variable "ebs_iops" {
  description = "Provisioned IOPS for EBS gp3 volumes"
  type        = number
  default     = 3000
}

variable "ebs_throughput" {
  description = "Provisioned throughput for EBS gp3 volumes (MiB/s)"
  type        = number
  default     = 125
}

variable "master_user" {
  description = "Master username for OpenSearch fine-grained access control"
  type        = string
  default     = "aisocadmin"
}

variable "create_service_linked_role" {
  description = "Whether to create the OpenSearch service-linked role (disable if already exists)"
  type        = bool
  default     = true
}

variable "log_retention_days" {
  description = "Number of days to retain OpenSearch logs in CloudWatch"
  type        = number
  default     = 90
}

variable "alarm_sns_topic_arns" {
  description = "SNS topic ARNs for CloudWatch alarms"
  type        = list(string)
  default     = []
}
