variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "ai-soc"
}

variable "aws_region" {
  description = "AWS region for resource deployment"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "prod"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "kubernetes_version" {
  description = "Kubernetes version for the EKS cluster"
  type        = string
  default     = "1.29"
}

variable "alarm_sns_topic_arn" {
  description = "SNS topic ARN for operational alarms"
  type        = string
  default     = ""
}

variable "authorized_iam_role_arns" {
  description = "Additional IAM role ARNs authorized to use KMS keys"
  type        = list(string)
  default     = []
}
