provider "aws" {
  region = "eu-central-1"
}

locals {
  prefix = "klochko-bohdan-04"
}

# S3 бакет для audit-log
resource "aws_s3_bucket" "audit_log" {
  bucket        = "${local.prefix}-audit-log"
  force_destroy = true # дозволяє видалити бакет з файлами при terraform destroy
}

# Блокування публічного доступу до бакету
resource "aws_s3_bucket_public_access_block" "audit_log" {
  bucket = aws_s3_bucket.audit_log.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

module "database" {
  source     = "../../modules/dynamodb"
  table_name = "${local.prefix}-tasks"
}

module "backend" {
  source              = "../../modules/lambda"
  function_name       = "${local.prefix}-tasks-handler"
  source_file         = "${path.root}/../../src/app.py"
  dynamodb_table_arn  = module.database.table_arn
  dynamodb_table_name = module.database.table_name
  log_bucket_name     = aws_s3_bucket.audit_log.bucket
  log_bucket_arn      = aws_s3_bucket.audit_log.arn
}

module "api" {
  source               = "../../modules/api_gateway"
  api_name             = "${local.prefix}-tasks-api"
  lambda_invoke_arn    = module.backend.invoke_arn
  lambda_function_name = module.backend.function_name
}

output "api_url" {
  value = module.api.api_endpoint
}

output "audit_log_bucket" {
  value = aws_s3_bucket.audit_log.bucket
}
