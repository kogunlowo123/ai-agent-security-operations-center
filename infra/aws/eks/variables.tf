variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "ai-soc"
}

variable "environment" {
  description = "Deployment environment (prod, staging, dev)"
  type        = string
}

variable "aws_region" {
  description = "AWS region for resource deployment"
  type        = string
  default     = "us-east-1"
}

variable "vpc_id" {
  description = "VPC ID where EKS cluster will be deployed"
  type        = string
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs for EKS worker nodes"
  type        = list(string)
}

variable "kubernetes_version" {
  description = "Kubernetes version for the EKS cluster"
  type        = string
  default     = "1.29"
}

variable "kms_key_arn" {
  description = "ARN of the KMS key for encrypting EKS secrets"
  type        = string
}

variable "cluster_endpoint_public_access" {
  description = "Whether to enable public access to the EKS API server endpoint"
  type        = bool
  default     = false
}

variable "cluster_endpoint_public_access_cidrs" {
  description = "CIDRs allowed to access the public EKS API server endpoint"
  type        = list(string)
  default     = []
}

variable "log_retention_days" {
  description = "Number of days to retain EKS control plane logs"
  type        = number
  default     = 90
}

# System node group
variable "system_node_instance_types" {
  description = "EC2 instance types for the system node group"
  type        = list(string)
  default     = ["m5.large", "m5a.large", "m5d.large"]
}

variable "system_node_desired_size" {
  description = "Desired number of nodes in the system node group"
  type        = number
  default     = 3
}

variable "system_node_max_size" {
  description = "Maximum number of nodes in the system node group"
  type        = number
  default     = 6
}

variable "system_node_min_size" {
  description = "Minimum number of nodes in the system node group"
  type        = number
  default     = 3
}

# Compute node group
variable "compute_node_instance_types" {
  description = "EC2 instance types for the compute node group (Spot)"
  type        = list(string)
  default     = ["m5.xlarge", "m5a.xlarge", "m5d.xlarge", "m4.xlarge", "m5n.xlarge"]
}

variable "compute_node_desired_size" {
  description = "Desired number of nodes in the compute node group"
  type        = number
  default     = 2
}

variable "compute_node_max_size" {
  description = "Maximum number of nodes in the compute node group"
  type        = number
  default     = 20
}

variable "compute_node_min_size" {
  description = "Minimum number of nodes in the compute node group"
  type        = number
  default     = 0
}
