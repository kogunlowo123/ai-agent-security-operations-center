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
    Component   = "s3"
  }

  buckets = {
    threat_intel = {
      name        = "${local.name}-threat-intel-${data.aws_caller_identity.current.account_id}"
      description = "Threat intelligence data and IOC feeds"
    }
    incident_artifacts = {
      name        = "${local.name}-incident-artifacts-${data.aws_caller_identity.current.account_id}"
      description = "Incident response artifacts and forensic data"
    }
    model_artifacts = {
      name        = "${local.name}-model-artifacts-${data.aws_caller_identity.current.account_id}"
      description = "ML model artifacts, weights, and configs"
    }
    audit_logs = {
      name        = "${local.name}-audit-logs-${data.aws_caller_identity.current.account_id}"
      description = "Audit trail and compliance logs"
    }
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Threat Intelligence Bucket
resource "aws_s3_bucket" "threat_intel" {
  bucket = local.buckets.threat_intel.name

  tags = merge(local.common_tags, {
    Name    = local.buckets.threat_intel.name
    Purpose = local.buckets.threat_intel.description
  })
}

resource "aws_s3_bucket_versioning" "threat_intel" {
  bucket = aws_s3_bucket.threat_intel.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "threat_intel" {
  bucket = aws_s3_bucket.threat_intel.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "threat_intel" {
  bucket                  = aws_s3_bucket.threat_intel.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "threat_intel" {
  bucket = aws_s3_bucket.threat_intel.id

  rule {
    id     = "transition-to-ia"
    status = "Enabled"

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER_IR"
    }

    expiration {
      days = 365
    }

    noncurrent_version_transition {
      noncurrent_days = 30
      storage_class   = "STANDARD_IA"
    }

    noncurrent_version_expiration {
      noncurrent_days = 90
    }
  }
}

resource "aws_s3_bucket_notification" "threat_intel" {
  count  = length(var.threat_intel_event_queue_arn) > 0 ? 1 : 0
  bucket = aws_s3_bucket.threat_intel.id

  queue {
    queue_arn     = var.threat_intel_event_queue_arn
    events        = ["s3:ObjectCreated:*"]
    filter_suffix = ".json"
  }
}

resource "aws_s3_bucket_logging" "threat_intel" {
  count         = var.enable_access_logging ? 1 : 0
  bucket        = aws_s3_bucket.threat_intel.id
  target_bucket = aws_s3_bucket.audit_logs.id
  target_prefix = "threat-intel/"
}

# Incident Artifacts Bucket
resource "aws_s3_bucket" "incident_artifacts" {
  bucket = local.buckets.incident_artifacts.name

  tags = merge(local.common_tags, {
    Name    = local.buckets.incident_artifacts.name
    Purpose = local.buckets.incident_artifacts.description
  })
}

resource "aws_s3_bucket_versioning" "incident_artifacts" {
  bucket = aws_s3_bucket.incident_artifacts.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "incident_artifacts" {
  bucket = aws_s3_bucket.incident_artifacts.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "incident_artifacts" {
  bucket                  = aws_s3_bucket.incident_artifacts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "incident_artifacts" {
  bucket = aws_s3_bucket.incident_artifacts.id

  rule {
    id     = "archive-artifacts"
    status = "Enabled"

    transition {
      days          = 60
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 180
      storage_class = "GLACIER"
    }

    expiration {
      days = 2555 # 7 years for compliance
    }

    noncurrent_version_transition {
      noncurrent_days = 30
      storage_class   = "STANDARD_IA"
    }

    noncurrent_version_expiration {
      noncurrent_days = 365
    }
  }
}

resource "aws_s3_bucket_logging" "incident_artifacts" {
  count         = var.enable_access_logging ? 1 : 0
  bucket        = aws_s3_bucket.incident_artifacts.id
  target_bucket = aws_s3_bucket.audit_logs.id
  target_prefix = "incident-artifacts/"
}

# Model Artifacts Bucket
resource "aws_s3_bucket" "model_artifacts" {
  bucket = local.buckets.model_artifacts.name

  tags = merge(local.common_tags, {
    Name    = local.buckets.model_artifacts.name
    Purpose = local.buckets.model_artifacts.description
  })
}

resource "aws_s3_bucket_versioning" "model_artifacts" {
  bucket = aws_s3_bucket.model_artifacts.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "model_artifacts" {
  bucket = aws_s3_bucket.model_artifacts.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "model_artifacts" {
  bucket                  = aws_s3_bucket.model_artifacts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "model_artifacts" {
  bucket = aws_s3_bucket.model_artifacts.id

  rule {
    id     = "manage-versions"
    status = "Enabled"

    noncurrent_version_transition {
      noncurrent_days = 60
      storage_class   = "STANDARD_IA"
    }

    noncurrent_version_expiration {
      noncurrent_days = 180
    }
  }
}

resource "aws_s3_bucket_logging" "model_artifacts" {
  count         = var.enable_access_logging ? 1 : 0
  bucket        = aws_s3_bucket.model_artifacts.id
  target_bucket = aws_s3_bucket.audit_logs.id
  target_prefix = "model-artifacts/"
}

# Audit Logs Bucket (server access logs destination)
resource "aws_s3_bucket" "audit_logs" {
  bucket = local.buckets.audit_logs.name

  tags = merge(local.common_tags, {
    Name    = local.buckets.audit_logs.name
    Purpose = local.buckets.audit_logs.description
  })
}

resource "aws_s3_bucket_versioning" "audit_logs" {
  bucket = aws_s3_bucket.audit_logs.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "audit_logs" {
  bucket = aws_s3_bucket.audit_logs.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "audit_logs" {
  bucket                  = aws_s3_bucket.audit_logs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "audit_logs" {
  bucket = aws_s3_bucket.audit_logs.id

  rule {
    id     = "retain-audit-logs"
    status = "Enabled"

    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 365
      storage_class = "GLACIER"
    }

    expiration {
      days = 2555 # 7 years for compliance
    }
  }
}

# Bucket Policy: deny non-HTTPS access
resource "aws_s3_bucket_policy" "threat_intel_https_only" {
  bucket = aws_s3_bucket.threat_intel.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyNonHTTPS"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.threat_intel.arn,
          "${aws_s3_bucket.threat_intel.arn}/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      }
    ]
  })
}

resource "aws_s3_bucket_policy" "incident_artifacts_https_only" {
  bucket = aws_s3_bucket.incident_artifacts.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyNonHTTPS"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.incident_artifacts.arn,
          "${aws_s3_bucket.incident_artifacts.arn}/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      }
    ]
  })
}

resource "aws_s3_bucket_policy" "model_artifacts_https_only" {
  bucket = aws_s3_bucket.model_artifacts.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyNonHTTPS"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.model_artifacts.arn,
          "${aws_s3_bucket.model_artifacts.arn}/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      }
    ]
  })
}
