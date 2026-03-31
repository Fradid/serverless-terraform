Лабораторна робота з розгортання безсерверної архітектури на AWS з використанням Terraform.

## Опис

Реалізація REST API трекера завдань (варіант 4) на основі безсерверної архітектури AWS:

```
Client → API Gateway → Lambda (Python 3.12) → DynamoDB
                                ↓
                               S3 (audit-log)
```

## Структура репозиторію

```
serverless-terraform/
├── src/
│   └── app.py                  # Lambda функція (Python 3.12)
├── modules/
│   ├── dynamodb/
│   │   └── main.tf             # Таблиця DynamoDB з GSI по полю status
│   ├── lambda/
│   │   └── main.tf             # Lambda функція + IAM роль + політики
│   └── api_gateway/
│       └── main.tf             # HTTP API Gateway v2
├── envs/
│   └── dev/
│       └── main.tf             # Середовище розгортання + S3 для audit-log
└── .gitignore
```

## Технології

- **AWS Lambda** — Python 3.12
- **Amazon API Gateway** — HTTP API v2
- **Amazon DynamoDB** — NoSQL з білінгом PAY_PER_REQUEST
- **Amazon S3** — зберігання audit-log
- **Terraform** — >= 1.10.0
- **AWS Provider** — ~> 5.0

## API ендпоінти

| Метод | Шлях | Опис |
|-------|------|------|
| `POST` | `/tasks` | Створення нового завдання |
| `GET` | `/tasks` | Отримання всіх завдань |
| `GET` | `/tasks?status=open` | Фільтрація завдань по статусу |
| `PUT` | `/tasks/{id}` | Оновлення статусу завдання |

### Поля завдання

```json
{
  "id": "uuid",
  "title": "Назва завдання",
  "priority": "low | medium | high",
  "status": "open | in_progress | done",
  "created_at": "2026-03-31T10:00:00"
}
```

## Передумови

- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.10.0
- [AWS CLI](https://aws.amazon.com/cli/) налаштований (`aws configure`)
- Існуючий S3 бакет для Terraform state

## Розгортання

### 1. Клонувати репозиторій

```bash
git clone https://github.com/Fradid/serverless-terraform.git
cd serverless-terraform
```

### 2. Налаштувати змінні

Відкрити `envs/dev/main.tf` та замінити:

```hcl
locals {
  prefix = "your-name-xx"  # власний префікс
}

backend "s3" {
  bucket = "your-existing-bucket"  # існуючий S3 бакет для state
}
```

### 3. Розгорнути інфраструктуру

```bash
cd envs/dev
terraform init
terraform plan
terraform apply
```

### 4. Отримати URL API

```bash
terraform output api_url
```

## Тестування

```bash
# Зберегти URL
export API_URL=$(terraform output -raw api_url)

# Створити завдання
curl -X POST $API_URL/tasks \
  -H "Content-Type: application/json" \
  -d '{"title": "Моє завдання", "priority": "high", "status": "open"}'

# Отримати всі завдання
curl -X GET $API_URL/tasks

# Фільтрація по статусу
curl -X GET "$API_URL/tasks?status=open"

# Оновити статус (підстав свій id)
curl -X PUT $API_URL/tasks/{id} \
  -H "Content-Type: application/json" \
  -d '{"status": "in_progress"}'

# Перевірити audit-log у S3
export BUCKET=$(terraform output -raw audit_log_bucket)
aws s3 ls s3://$BUCKET/logs/ --recursive
```

## Видалення інфраструктури

```bash
terraform destroy
```

## Архітектурні рішення

- **PAY_PER_REQUEST** білінг DynamoDB — оплата лише за фактичні запити, ідеально для безсерверної архітектури
- **GSI по полю `status`** — ефективна фільтрація завдань без повного сканування таблиці
- **S3 audit-log** — кожна операція (`CREATE_TASK`, `UPDATE_TASK_STATUS`) записується в окремий JSON файл
- **Terraform Monorepo** — модульна структура з розділенням на `modules/` та `envs/`
- **S3 backend з `use_lockfile`** — безпечне зберігання Terraform state без потреби в DynamoDB для блокувань (Terraform >= 1.10.0)
- **Мінімальні IAM права** — Lambda має доступ лише до необхідних операцій DynamoDB та `s3:PutObject` в папку `logs/*`