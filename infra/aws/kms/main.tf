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
    Component   = "kms"
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Database KMS Key (Aurora)
resource "aws_kms_key" "database" {
  description             = "${local.name} - Database encryption key for Aurora PostgreSQL"
  deletion_window_in_days = var.key_deletion_window_days
  enable_key_rotation     = true
  multi_region            = var.enable_multi_region_keys

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow RDS Service"
        Effect = "Allow"
        Principal = {
          Service = "rds.amazonaws.com"
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey",
          "kms:CreateGrant"
        ]
        Resource = "*"
      },
      {
        Sid    = "Allow Authorized IAM Roles"
        Effect = "Allow"
        Principal = {
          AWS = var.authorized_iam_role_arns
        }
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey",
          "kms:GenerateDataKey"
        ]
        Resource = "*"
      }
    ]
  })

  tags = merge(local.common_tags, {
    Name    = "${local.name}-database-key"
    Purpose = "Aurora PostgreSQL encryption"
  })
}

resource "aws_kms_alias" "database" {
  name          = "alias/${local.name}/database"
  target_key_id = aws_kms_key.database.key_id
}

# S3 KMS Key
resource "aws_kms_key" "s3" {
  description             = "${local.name} - S3 encryption key for object storage"
  deletion_window_in_days = var.key_deletion_window_days
  enable_key_rotation     = true
  multi_region            = var.enable_multi_region_keys

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow S3 Service"
        Effect = "Allow"
        Principal = {
          Service = "s3.amazonaws.com"
        }
        Action = [
          "kms:GenerateDataKey",
          "kms:Decrypt",
          "kms:DescribeKey"
        ]
        Resource = "*"
      },
      {
        Sid    = "Allow Delivery Services"
        Effect = "Allow"
        Principal = {
          Service = [
            "cloudtrail.amazonaws.com",
            "logs.amazonaws.com",
            "delivery.logs.amazonaws.com"
          ]
        }
        Action = [
          "kms:GenerateDataKey",
          "kms:Decrypt",
          "kms:DescribeKey"
        ]
        Resource = "*"
      },
      {
        Sid    = "Allow Authorized IAM Roles"
        Effect = "Allow"
        Principal = {
          AWS = var.authorized_iam_role_arns
        }
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey",
          "kms:GenerateDataKey",
          "kms:ReEncrypt*"
        ]
        Resource = "*"
      }
    ]
  })

  tags = merge(local.common_tags, {
    Name    = "${local.name}-s3-key"
    Purpose = "S3 bucket encryption"
  })
}

resource "aws_kms_alias" "s3" {
  name          = "alias/${local.name}/s3"
  target_key_id = aws_kms_key.s3.key_id
}

# Secrets Manager KMS Key
resource "aws_kms_key" "secrets" {
  description             = "${local.name} - Secrets Manager encryption key"
  deletion_window_in_days = var.key_deletion_window_days
  enable_key_rotation     = true
  multi_region            = var.enable_multi_region_keys

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow Secrets Manager"
        Effect = "Allow"
        Principal = {
          Service = "secretsmanager.amazonaws.com"
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey",
          "kms:CreateGrant"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "kms:CallerAccount" = data.aws_caller_identity.current.account_id
          }
        }
      },
      {
        Sid    = "Allow Authorized IAM Roles"
        Effect = "Allow"
        Principal = {
          AWS = var.authorized_iam_role_arns
        }
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey",
          "kms:GenerateDataKey"
        ]
        Resource = "*"
      }
    ]
  })

  tags = merge(local.common_tags, {
    Name    = "${local.name}-secrets-key"
    Purpose = "Secrets Manager encryption"
  })
}

resource "aws_kms_alias" "secrets" {
  name          = "alias/${local.name}/secrets"
  target_key_id = aws_kms_key.secrets.key_id
}

# EKS KMS Key (for Kubernetes secrets encryption)
resource "aws_kms_key" "eks" {
  description             = "${local.name} - EKS secrets encryption key"
  deletion_window_in_days = var.key_deletion_window_days
  enable_key_rotation     = true
  multi_region            = false # EKS encryption doesn't support multi-region

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow EKS Service"
        Effect = "Allow"
        Principal = {
          Service = "eks.amazonaws.com"
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ListGrants",
          "kms:DescribeKey",
          "kms:CreateGrant"
        ]
        Resource = "*"
      },
      {
        Sid    = "Allow Authorized IAM Roles"
        Effect = "Allow"
        Principal = {
          AWS = var.authorized_iam_role_arns
        }
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey"
        ]
        Resource = "*"
      }
    ]
  })

  tags = merge(local.common_tags, {
    Name    = "${local.name}-eks-key"
    Purpose = "EKS Kubernetes secrets encryption"
  })
}

resource "aws_kms_alias" "eks" {
  name          = "alias/${local.name}/eks"
  target_key_id = aws_kms_key.eks.key_id
}

# SQS KMS Key
resource "aws_kms_key" "sqs" {
  description             = "${local.name} - SQS queue encryption key"
  deletion_window_in_days = var.key_deletion_window_days
  enable_key_rotation     = true
  multi_region            = false

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow SQS Service"
        Effect = "Allow"
        Principal = {
          Service = "sqs.amazonaws.com"
        }
        Action = [
          "kms:GenerateDataKey",
          "kms:Decrypt",
          "kms:DescribeKey"
        ]
        Resource = "*"
      },
      {
        Sid    = "Allow S3 to publish to SQS"
        Effect = "Allow"
        Principal = {
          Service = "s3.amazonaws.com"
        }
        Action = [
          "kms:GenerateDataKey",
          "kms:Decrypt"
        ]
        Resource = "*"
      },
      {
        Sid    = "Allow Authorized IAM Roles"
        Effect = "Allow"
        Principal = {
          AWS = var.authorized_iam_role_arns
        }
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey",
          "kms:GenerateDataKey"
        ]
        Resource = "*"
      }
    ]
  })

  tags = merge(local.common_tags, {
    Name    = "${local.name}-sqs-key"
    Purpose = "SQS queue encryption"
  })
}

resource "aws_kms_alias" "sqs" {
  name          = "alias/${local.name}/sqs"
  target_key_id = aws_kms_key.sqs.key_id
}

# CloudWatch Alarms for KMS key usage
resource "aws_cloudwatch_metric_alarm" "kms_key_deleted" {
  for_each = {
    database = aws_kms_key.database.key_id
    s3       = aws_kms_key.s3.key_id
    secrets  = aws_kms_key.secrets.key_id
    eks      = aws_kms_key.eks.key_id
  }

  alarm_name          = "${local.name}-kms-${each.key}-pending-deletion"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "NumberOfRequestsForKeyInPendingDeletion"
  namespace           = "AWS/KMS"
  period              = 300
  statistic           = "Sum"
  threshold           = 1
  alarm_description   = "KMS ${each.key} key is pending deletion and still receiving API requests"
  alarm_actions       = var.alarm_sns_topic_arns
  treat_missing_data  = "notBreaching"

  dimensions = {
    KeyId = each.value
  }

  tags = local.common_tags
}
