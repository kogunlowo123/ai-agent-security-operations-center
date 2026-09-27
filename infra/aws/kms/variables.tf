variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "ai-soc"
}

variable "environment" {
  description = "Deployment environment (prod, staging, dev)"
  type        = string
}

variable "authorized_iam_role_arns" {
  description = "IAM role ARNs authorized to use KMS keys"
  type        = list(string)
  default     = []
}

variable "key_deletion_window_days" {
  description = "Number of days before a KMS key is deleted after scheduling deletion"
  type        = number
  default     = 30
  validation {
    condition     = var.key_deletion_window_days >= 7 && var.key_deletion_window_days <= 30
    error_message = "Key deletion window must be between 7 and 30 days."
  }
}

variable "enable_multi_region_keys" {
  description = "Whether to create multi-region KMS keys for cross-region replication"
  type        = bool
  default     = false
}

variable "alarm_sns_topic_arns" {
  description = "SNS topic ARNs for CloudWatch alarms"
  type        = list(string)
  default     = []
}
