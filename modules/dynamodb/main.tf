variable "table_name" {
  description = "The unique name of the DynamoDB table"
  type        = string
}
resource "aws_dynamodb_table" "main" {
  name         = var.table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"
  attribute {
    name = "id"
    type = "S"
  }
}
output "table_name" {
  value = aws_dynamodb_table.main.name
}
output "table_arn" {
  value = aws_dynamodb_table.main.arn
}
