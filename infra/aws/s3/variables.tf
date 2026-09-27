variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "ai-soc"
}

variable "environment" {
  description = "Deployment environment (prod, staging, dev)"
  type        = string
}

variable "kms_key_arn" {
  description = "ARN of the KMS key for S3 encryption"
  type        = string
}

variable "enable_access_logging" {
  description = "Enable server access logging for all buckets"
  type        = bool
  default     = true
}

variable "threat_intel_event_queue_arn" {
  description = "SQS queue ARN for S3 event notifications from threat intel bucket"
  type        = string
  default     = ""
}
