terraform {
  backend "azurerm" {
    resource_group_name  = "rg-ai-soc-tfstate"
    storage_account_name = "staisoctfstateprod"
    container_name       = "tfstate"
    key                  = "azure/prod/terraform.tfstate"

    # Use Azure AD authentication (no access key stored in config)
    use_azuread_auth = true
  }
}
