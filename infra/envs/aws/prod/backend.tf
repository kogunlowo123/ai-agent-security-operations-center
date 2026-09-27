terraform {
  backend "s3" {
    bucket         = "ai-soc-terraform-state-prod"
    key            = "aws/prod/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    kms_key_id     = "alias/ai-soc/s3"
    dynamodb_table = "ai-soc-terraform-locks-prod"

    # Prevent accidental deletion
    force_path_style = false
  }
}
