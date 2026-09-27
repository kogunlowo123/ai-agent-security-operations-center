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
  description = "ARN of the KMS key for SQS encryption"
  type        = string
}

variable "message_retention_seconds" {
  description = "Number of seconds SQS retains a message"
  type        = number
  default     = 345600 # 4 days
}

variable "triage_visibility_timeout" {
  description = "Visibility timeout for the triage queue (seconds)"
  type        = number
  default     = 300 # 5 minutes for triage processing
}

variable "hunt_visibility_timeout" {
  description = "Visibility timeout for the hunt queue (seconds)"
  type        = number
  default     = 900 # 15 minutes for hunt tasks
}

variable "incident_visibility_timeout" {
  description = "Visibility timeout for the incident queue (seconds)"
  type        = number
  default     = 600 # 10 minutes for incident response
}

variable "allowed_sender_role_arns" {
  description = "IAM role ARNs allowed to send/receive messages"
  type        = list(string)
  default     = []
}

variable "alarm_sns_topic_arns" {
  description = "SNS topic ARNs for CloudWatch alarms"
  type        = list(string)
  default     = []
}

variable "triage_queue_depth_alarm_threshold" {
  description = "Triage queue message depth threshold for alarming"
  type        = number
  default     = 1000
}
