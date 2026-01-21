resource "azurerm_resource_group" "this" {
  name     = "${var.project_name}-${var.environment}-rg"
  location = var.location
}

resource "azurerm_storage_account" "this" {
  name                     = lower(replace("${var.project_name}${var.environment}", "-", ""))
  resource_group_name      = azurerm_resource_group.this.name
  location                 = var.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
}

resource "azurerm_storage_container" "tricloud_container" {
  name                  = "tricloud-vault"
  storage_account_name  = azurerm_storage_account.this.name
  container_access_type = "private"
}

