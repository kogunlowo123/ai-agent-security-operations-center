output "domain_name" {
  description = "Name of the OpenSearch domain"
  value       = aws_opensearch_domain.main.domain_name
}

output "domain_arn" {
  description = "ARN of the OpenSearch domain"
  value       = aws_opensearch_domain.main.arn
}

output "domain_id" {
  description = "ID of the OpenSearch domain"
  value       = aws_opensearch_domain.main.domain_id
}

output "endpoint" {
  description = "Domain-specific endpoint for the OpenSearch domain"
  value       = aws_opensearch_domain.main.endpoint
}

output "kibana_endpoint" {
  description = "Domain-specific endpoint for OpenSearch Dashboards (formerly Kibana)"
  value       = aws_opensearch_domain.main.dashboard_endpoint
}

output "security_group_id" {
  description = "ID of the security group for the OpenSearch domain"
  value       = aws_security_group.opensearch.id
}

output "credentials_secret_arn" {
  description = "ARN of the Secrets Manager secret with OpenSearch credentials"
  value       = aws_secretsmanager_secret.opensearch_credentials.arn
}

output "engine_version" {
  description = "OpenSearch engine version"
  value       = aws_opensearch_domain.main.engine_version
}
