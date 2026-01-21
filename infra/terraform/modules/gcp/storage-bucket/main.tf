resource "google_storage_bucket" "this" {
  name     = "${var.project_name}-${var.environment}-gcp"
  location = "ASIA"
}
