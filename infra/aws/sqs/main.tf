terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

locals {
  name = "${var.environment}-${var.project_name}"

  common_tags = {
    Environment = var.environment
    Project     = var.project_name
    ManagedBy   = "terraform"
    Component   = "sqs"
  }

  queues = {
    triage = {
      name        = "${local.name}-triage-queue"
      description = "Queue for security alert triage processing"
      max_receive_count = 5
    }
    hunt = {
      name        = "${local.name}-hunt-queue"
      description = "Queue for threat hunting tasks"
      max_receive_count = 3
    }
    incident = {
      name        = "${local.name}-incident-queue"
      description = "Queue for incident response actions"
      max_receive_count = 3
    }
  }
}

# Dead Letter Queues
resource "aws_sqs_queue" "triage_dlq" {
  name                      = "${local.name}-triage-dlq"
  message_retention_seconds = 1209600 # 14 days
  kms_master_key_id         = var.kms_key_arn

  tags = merge(local.common_tags, {
    Name    = "${local.name}-triage-dlq"
    Purpose = "Dead-letter queue for triage queue"
  })
}

resource "aws_sqs_queue" "hunt_dlq" {
  name                      = "${local.name}-hunt-dlq"
  message_retention_seconds = 1209600
  kms_master_key_id         = var.kms_key_arn

  tags = merge(local.common_tags, {
    Name    = "${local.name}-hunt-dlq"
    Purpose = "Dead-letter queue for hunt queue"
  })
}

resource "aws_sqs_queue" "incident_dlq" {
  name                      = "${local.name}-incident-dlq"
  message_retention_seconds = 1209600
  kms_master_key_id         = var.kms_key_arn

  tags = merge(local.common_tags, {
    Name    = "${local.name}-incident-dlq"
    Purpose = "Dead-letter queue for incident queue"
  })
}

# Triage Queue
resource "aws_sqs_queue" "triage" {
  name                       = local.queues.triage.name
  visibility_timeout_seconds = var.triage_visibility_timeout
  message_retention_seconds  = var.message_retention_seconds
  receive_wait_time_seconds  = 20  # Long polling
  delay_seconds              = 0
  max_message_size           = 262144  # 256 KB
  kms_master_key_id          = var.kms_key_arn

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.triage_dlq.arn
    maxReceiveCount     = local.queues.triage.max_receive_count
  })

  tags = merge(local.common_tags, {
    Name    = local.queues.triage.name
    Purpose = local.queues.triage.description
  })
}

# Hunt Queue
resource "aws_sqs_queue" "hunt" {
  name                       = local.queues.hunt.name
  visibility_timeout_seconds = var.hunt_visibility_timeout
  message_retention_seconds  = var.message_retention_seconds
  receive_wait_time_seconds  = 20
  delay_seconds              = 0
  max_message_size           = 262144
  kms_master_key_id          = var.kms_key_arn

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.hunt_dlq.arn
    maxReceiveCount     = local.queues.hunt.max_receive_count
  })

  tags = merge(local.common_tags, {
    Name    = local.queues.hunt.name
    Purpose = local.queues.hunt.description
  })
}

# Incident Queue
resource "aws_sqs_queue" "incident" {
  name                       = local.queues.incident.name
  visibility_timeout_seconds = var.incident_visibility_timeout
  message_retention_seconds  = var.message_retention_seconds
  receive_wait_time_seconds  = 20
  delay_seconds              = 0
  max_message_size           = 262144
  kms_master_key_id          = var.kms_key_arn

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.incident_dlq.arn
    maxReceiveCount     = local.queues.incident.max_receive_count
  })

  tags = merge(local.common_tags, {
    Name    = local.queues.incident.name
    Purpose = local.queues.incident.description
  })
}

# Queue Policies
resource "aws_sqs_queue_policy" "triage" {
  queue_url = aws_sqs_queue.triage.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowS3Events"
        Effect = "Allow"
        Principal = {
          Service = "s3.amazonaws.com"
        }
        Action   = "sqs:SendMessage"
        Resource = aws_sqs_queue.triage.arn
        Condition = {
          ArnLike = {
            "aws:SourceArn" = "arn:aws:s3:::*"
          }
        }
      },
      {
        Sid    = "AllowAuthorizedSenders"
        Effect = "Allow"
        Principal = {
          AWS = var.allowed_sender_role_arns
        }
        Action = [
          "sqs:SendMessage",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:ChangeMessageVisibility"
        ]
        Resource = aws_sqs_queue.triage.arn
      },
      {
        Sid       = "DenyNonHTTPS"
        Effect    = "Deny"
        Principal = "*"
        Action    = "sqs:*"
        Resource  = aws_sqs_queue.triage.arn
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      }
    ]
  })
}

resource "aws_sqs_queue_policy" "hunt" {
  queue_url = aws_sqs_queue.hunt.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowAuthorizedSenders"
        Effect = "Allow"
        Principal = {
          AWS = var.allowed_sender_role_arns
        }
        Action = [
          "sqs:SendMessage",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:ChangeMessageVisibility"
        ]
        Resource = aws_sqs_queue.hunt.arn
      },
      {
        Sid       = "DenyNonHTTPS"
        Effect    = "Deny"
        Principal = "*"
        Action    = "sqs:*"
        Resource  = aws_sqs_queue.hunt.arn
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      }
    ]
  })
}

resource "aws_sqs_queue_policy" "incident" {
  queue_url = aws_sqs_queue.incident.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowAuthorizedSenders"
        Effect = "Allow"
        Principal = {
          AWS = var.allowed_sender_role_arns
        }
        Action = [
          "sqs:SendMessage",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:ChangeMessageVisibility"
        ]
        Resource = aws_sqs_queue.incident.arn
      },
      {
        Sid       = "DenyNonHTTPS"
        Effect    = "Deny"
        Principal = "*"
        Action    = "sqs:*"
        Resource  = aws_sqs_queue.incident.arn
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      }
    ]
  })
}

# CloudWatch Alarms for DLQs
resource "aws_cloudwatch_metric_alarm" "triage_dlq_depth" {
  alarm_name          = "${local.name}-triage-dlq-depth"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Sum"
  threshold           = 1
  alarm_description   = "Messages appearing in triage DLQ"
  alarm_actions       = var.alarm_sns_topic_arns

  dimensions = {
    QueueName = aws_sqs_queue.triage_dlq.name
  }

  tags = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "hunt_dlq_depth" {
  alarm_name          = "${local.name}-hunt-dlq-depth"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Sum"
  threshold           = 1
  alarm_description   = "Messages appearing in hunt DLQ"
  alarm_actions       = var.alarm_sns_topic_arns

  dimensions = {
    QueueName = aws_sqs_queue.hunt_dlq.name
  }

  tags = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "incident_dlq_depth" {
  alarm_name          = "${local.name}-incident-dlq-depth"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Sum"
  threshold           = 1
  alarm_description   = "Messages appearing in incident DLQ"
  alarm_actions       = var.alarm_sns_topic_arns

  dimensions = {
    QueueName = aws_sqs_queue.incident_dlq.name
  }

  tags = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "triage_queue_depth_high" {
  alarm_name          = "${local.name}-triage-queue-depth-high"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 2
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Maximum"
  threshold           = var.triage_queue_depth_alarm_threshold
  alarm_description   = "Triage queue depth is unusually high"
  alarm_actions       = var.alarm_sns_topic_arns

  dimensions = {
    QueueName = aws_sqs_queue.triage.name
  }

  tags = local.common_tags
}
