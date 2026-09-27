output "api_service_role_arn" {
  description = "ARN of the API service IAM role"
  value       = aws_iam_role.api_service.arn
}

output "api_service_role_name" {
  description = "Name of the API service IAM role"
  value       = aws_iam_role.api_service.name
}

output "agent_runtime_role_arn" {
  description = "ARN of the agent runtime IAM role"
  value       = aws_iam_role.agent_runtime.arn
}

output "agent_runtime_role_name" {
  description = "Name of the agent runtime IAM role"
  value       = aws_iam_role.agent_runtime.name
}

output "bedrock_invoke_role_arn" {
  description = "ARN of the Bedrock invoke IAM role"
  value       = aws_iam_role.bedrock_invoke.arn
}

output "bedrock_invoke_role_name" {
  description = "Name of the Bedrock invoke IAM role"
  value       = aws_iam_role.bedrock_invoke.name
}

output "all_role_arns" {
  description = "Map of all IAM role ARNs"
  value = {
    api_service     = aws_iam_role.api_service.arn
    agent_runtime   = aws_iam_role.agent_runtime.arn
    bedrock_invoke  = aws_iam_role.bedrock_invoke.arn
  }
}
