resource "aws_s3_bucket" "this" {
  bucket = "${var.project_name}-${var.environment}-aws"
}

resource "aws_s3_bucket_cors_configuration" "tricloud_cors" {
  bucket = aws_s3_bucket.this.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["PUT", "POST", "GET"]
    allowed_origins = [
      "http://localhost:5500",
      "http://127.0.0.1:5500",
      "https://urban-chainsaw-r49qv7gvx57c955-5500.app.github.dev"
    ]
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}
