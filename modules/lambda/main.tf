
variable "function_name" { type = string }
variable "source_file" { type = string }
variable "dynamodb_table_arn" { type = string }
variable "dynamodb_table_name" { type = string }

# Автоматична генерація ZIP-архіву з вихідного коду Python
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_file = var.source_file
  output_path = "${path.module}/app.zip"
}

# Створення унікальної IAM-ролі виконання (Execution Role)
resource "aws_iam_role" "lambda_exec" {
  name = "${var.function_name}_role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

# Прикріплення базової політики для відправки логів у CloudWatch
resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/servicerole/AWSLambdaBasicExecutionRole"
}

# Створення гранулярної кастомної політики доступу до DynamoDB
resource "aws_iam_role_policy" "dynamodb_access" {
  name = "dynamodb_access_policy"
  role = aws_iam_role.lambda_exec.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["dynamodb:*"]
      Resource = var.dynamodb_table_arn
    }]
  })
}

# Конфігурація середовища виконання AWS Lambda
resource "aws_lambda_function" "api_handler" {
  filename      = data.archive_file.lambda_zip.output_path
  function_name = var.function_name
  role          = aws_iam_role.lambda_exec.arn
  handler       = "app.handler"
  runtime       = "python3.12"
  # Захист від зайвих деплоїв: оновлюється лише при зміні хешу файлу
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  environment {
    variables = {
      TABLE_NAME = var.dynamodb_table_name
    }
  }
}

output "invoke_arn" { value = aws_lambda_function.api_handler.invoke_arn }
output "function_name" { value = aws_lambda_function.api_handler.function_name }