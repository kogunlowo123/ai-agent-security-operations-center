output "triage_queue_url" {
  description = "URL of the triage SQS queue"
  value       = aws_sqs_queue.triage.url
}

output "triage_queue_arn" {
  description = "ARN of the triage SQS queue"
  value       = aws_sqs_queue.triage.arn
}

output "triage_queue_name" {
  description = "Name of the triage SQS queue"
  value       = aws_sqs_queue.triage.name
}

output "hunt_queue_url" {
  description = "URL of the hunt SQS queue"
  value       = aws_sqs_queue.hunt.url
}

output "hunt_queue_arn" {
  description = "ARN of the hunt SQS queue"
  value       = aws_sqs_queue.hunt.arn
}

output "hunt_queue_name" {
  description = "Name of the hunt SQS queue"
  value       = aws_sqs_queue.hunt.name
}

output "incident_queue_url" {
  description = "URL of the incident SQS queue"
  value       = aws_sqs_queue.incident.url
}

output "incident_queue_arn" {
  description = "ARN of the incident SQS queue"
  value       = aws_sqs_queue.incident.arn
}

output "incident_queue_name" {
  description = "Name of the incident SQS queue"
  value       = aws_sqs_queue.incident.name
}

output "triage_dlq_arn" {
  description = "ARN of the triage dead-letter queue"
  value       = aws_sqs_queue.triage_dlq.arn
}

output "hunt_dlq_arn" {
  description = "ARN of the hunt dead-letter queue"
  value       = aws_sqs_queue.hunt_dlq.arn
}

output "incident_dlq_arn" {
  description = "ARN of the incident dead-letter queue"
  value       = aws_sqs_queue.incident_dlq.arn
}

output "all_queue_arns" {
  description = "All main queue ARNs"
  value = [
    aws_sqs_queue.triage.arn,
    aws_sqs_queue.hunt.arn,
    aws_sqs_queue.incident.arn
  ]
}
