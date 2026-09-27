output "threat_intel_bucket_name" {
  description = "Name of the threat intelligence S3 bucket"
  value       = aws_s3_bucket.threat_intel.bucket
}

output "threat_intel_bucket_arn" {
  description = "ARN of the threat intelligence S3 bucket"
  value       = aws_s3_bucket.threat_intel.arn
}

output "incident_artifacts_bucket_name" {
  description = "Name of the incident artifacts S3 bucket"
  value       = aws_s3_bucket.incident_artifacts.bucket
}

output "incident_artifacts_bucket_arn" {
  description = "ARN of the incident artifacts S3 bucket"
  value       = aws_s3_bucket.incident_artifacts.arn
}

output "model_artifacts_bucket_name" {
  description = "Name of the model artifacts S3 bucket"
  value       = aws_s3_bucket.model_artifacts.bucket
}

output "model_artifacts_bucket_arn" {
  description = "ARN of the model artifacts S3 bucket"
  value       = aws_s3_bucket.model_artifacts.arn
}

output "audit_logs_bucket_name" {
  description = "Name of the audit logs S3 bucket"
  value       = aws_s3_bucket.audit_logs.bucket
}

output "audit_logs_bucket_arn" {
  description = "ARN of the audit logs S3 bucket"
  value       = aws_s3_bucket.audit_logs.arn
}

output "all_bucket_arns" {
  description = "ARNs of all created S3 buckets"
  value = [
    aws_s3_bucket.threat_intel.arn,
    aws_s3_bucket.incident_artifacts.arn,
    aws_s3_bucket.model_artifacts.arn,
    aws_s3_bucket.audit_logs.arn
  ]
}
