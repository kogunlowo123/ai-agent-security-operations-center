terraform {
  backend "gcs" {
    bucket = "ai-soc-tfstate-prod"
    prefix = "gcp/prod"
  }
}
