resource "aws_s3_bucket" "this" {
  bucket = "${var.project_name}-${var.environment}-aws"
}
