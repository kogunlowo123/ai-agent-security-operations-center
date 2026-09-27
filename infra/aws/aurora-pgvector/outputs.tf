output "endpoint" {
  description = "Writer endpoint of the Aurora cluster"
  value       = aws_rds_cluster.main.endpoint
}

output "reader_endpoint" {
  description = "Reader endpoint of the Aurora cluster"
  value       = aws_rds_cluster.main.reader_endpoint
}

output "port" {
  description = "Port the Aurora cluster listens on"
  value       = aws_rds_cluster.main.port
}

output "db_name" {
  description = "Name of the default database"
  value       = aws_rds_cluster.main.database_name
}

output "cluster_identifier" {
  description = "Identifier of the Aurora cluster"
  value       = aws_rds_cluster.main.cluster_identifier
}

output "cluster_arn" {
  description = "ARN of the Aurora cluster"
  value       = aws_rds_cluster.main.arn
}

output "cluster_resource_id" {
  description = "Resource ID of the Aurora cluster"
  value       = aws_rds_cluster.main.cluster_resource_id
}

output "master_username" {
  description = "Master username for the Aurora cluster"
  value       = aws_rds_cluster.main.master_username
  sensitive   = true
}

output "secret_arn" {
  description = "ARN of the Secrets Manager secret holding database credentials"
  value       = aws_secretsmanager_secret.master_password.arn
}

output "security_group_id" {
  description = "ID of the security group for Aurora"
  value       = aws_security_group.aurora.id
}

output "instance_identifiers" {
  description = "List of Aurora instance identifiers"
  value       = aws_rds_cluster_instance.main[*].identifier
}
