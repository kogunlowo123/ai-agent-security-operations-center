output "database_key_arn" {
  description = "ARN of the KMS key for database encryption"
  value       = aws_kms_key.database.arn
}

output "database_key_id" {
  description = "ID of the KMS key for database encryption"
  value       = aws_kms_key.database.key_id
}

output "database_key_alias" {
  description = "Alias of the KMS key for database encryption"
  value       = aws_kms_alias.database.name
}

output "s3_key_arn" {
  description = "ARN of the KMS key for S3 encryption"
  value       = aws_kms_key.s3.arn
}

output "s3_key_id" {
  description = "ID of the KMS key for S3 encryption"
  value       = aws_kms_key.s3.key_id
}

output "s3_key_alias" {
  description = "Alias of the KMS key for S3 encryption"
  value       = aws_kms_alias.s3.name
}

output "secrets_key_arn" {
  description = "ARN of the KMS key for Secrets Manager"
  value       = aws_kms_key.secrets.arn
}

output "secrets_key_id" {
  description = "ID of the KMS key for Secrets Manager"
  value       = aws_kms_key.secrets.key_id
}

output "secrets_key_alias" {
  description = "Alias of the KMS key for Secrets Manager"
  value       = aws_kms_alias.secrets.name
}

output "eks_key_arn" {
  description = "ARN of the KMS key for EKS secrets encryption"
  value       = aws_kms_key.eks.arn
}

output "eks_key_id" {
  description = "ID of the KMS key for EKS secrets encryption"
  value       = aws_kms_key.eks.key_id
}

output "sqs_key_arn" {
  description = "ARN of the KMS key for SQS encryption"
  value       = aws_kms_key.sqs.arn
}

output "sqs_key_id" {
  description = "ID of the KMS key for SQS encryption"
  value       = aws_kms_key.sqs.key_id
}

output "all_key_arns" {
  description = "Map of all KMS key ARNs by purpose"
  value = {
    database = aws_kms_key.database.arn
    s3       = aws_kms_key.s3.arn
    secrets  = aws_kms_key.secrets.arn
    eks      = aws_kms_key.eks.arn
    sqs      = aws_kms_key.sqs.arn
  }
}
