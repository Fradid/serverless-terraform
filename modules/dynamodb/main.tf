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

  # Додатковий атрибут для GSI фільтрації по статусу
  attribute {
    name = "status"
    type = "S"
  }

  # Global Secondary Index для ефективних запитів GET /tasks?status=open
  global_secondary_index {
    name            = "status-index"
    hash_key        = "status"
    projection_type = "ALL"
  }
}

output "table_name" {
  value = aws_dynamodb_table.main.name
}

output "table_arn" {
  value = aws_dynamodb_table.main.arn
}