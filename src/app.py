import json
import boto3
import os
import uuid
from datetime import datetime

TABLE_NAME = os.environ.get("TABLE_NAME")
LOG_BUCKET = os.environ.get("LOG_BUCKET")

if not TABLE_NAME:
    raise ValueError("TABLE_NAME environment variable is not set")
if not LOG_BUCKET:
    raise ValueError("LOG_BUCKET environment variable is not set")

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)
s3 = boto3.client("s3")
comprehend = boto3.client("comprehend")


def write_audit_log(action, data):
    """Записує audit-log у S3"""
    log_entry = {
        "action": action,
        "data": data,
        "timestamp": datetime.now().isoformat()
    }
    key = f"logs/{datetime.now().strftime('%Y-%m-%d')}/{uuid.uuid4()}.json"
    s3.put_object(
        Bucket=LOG_BUCKET,
        Key=key,
        Body=json.dumps(log_entry, ensure_ascii=False),
        ContentType="application/json"
    )


def handler(event, context):
    try:
        http_method = event.get("httpMethod", "")
        path = event.get("path", "")
        query_params = event.get("queryStringParameters") or {}
        proxy = (event.get("pathParameters") or {}).get("proxy", "")
        path_parts = proxy.split("/")
        task_id = path_parts[1] if len(path_parts) > 1 else None

        # POST /tasks — створення завдання
        if http_method == "POST" and path == "/tasks":
            body = json.loads(event.get("body") or "{}")

            if not body.get("title"):
                return {
                    "statusCode": 400,
                    "body": json.dumps({"message": "Field 'title' is required"})
                }

            task_id = str(uuid.uuid4())
            task = {
                "id": task_id,
                "title": body.get("title"),
                "priority": body.get("priority", "medium"),
                "status": body.get("status", "open"),
                "created_at": datetime.now().isoformat()
            }
            table.put_item(Item=task)
            write_audit_log("CREATE_TASK", task)

            return {
                "statusCode": 201,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"message": "Task created", "task": task})
            }

        # POST /tasks/{id}/prioritize — автопріоритет за тональністю
        elif http_method == "POST" and task_id and len(path_parts) == 3 and path_parts[2] == "prioritize":
            result = table.get_item(Key={"id": task_id})
            task = result.get("Item")

            if not task:
                return {
                    "statusCode": 404,
                    "body": json.dumps({"message": "Task not found"})
                }

            try:
                title = task.get("title", "")
                sentiment_result = comprehend.detect_sentiment(
                    Text=title,
                    LanguageCode="en"
                )
                sentiment = sentiment_result["Sentiment"]
                score = sentiment_result["SentimentScore"]

                # Негативна тональність → підвищуємо пріоритет до high
                new_priority = task.get("priority", "medium")
                if sentiment == "NEGATIVE":
                    new_priority = "high"

                update_result = table.update_item(
                    Key={"id": task_id},
                    UpdateExpression="SET priority = :priority, sentiment = :sentiment, sentiment_score = :score, updated_at = :updated_at",
                    ExpressionAttributeValues={
                        ":priority": new_priority,
                        ":sentiment": sentiment,
                        ":score": str(score),
                        ":updated_at": datetime.now().isoformat()
                    },
                    ReturnValues="ALL_NEW"
                )
                updated_task = update_result.get("Attributes", {})
                write_audit_log("PRIORITIZE_TASK", {
                    "id": task_id,
                    "sentiment": sentiment,
                    "new_priority": new_priority
                })

                return {
                    "statusCode": 200,
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps({
                        "message": "Task prioritized",
                        "sentiment": sentiment,
                        "new_priority": new_priority,
                        "task": updated_task
                    })
                }

            except Exception as ai_error:
                # Graceful degradation — якщо Comprehend недоступний
                print(f"Comprehend error: {str(ai_error)}")
                return {
                    "statusCode": 200,
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps({
                        "message": "Prioritization unavailable, task unchanged",
                        "task": task
                    })
                }

        # PUT /tasks/{id} — оновлення статусу
        elif http_method == "PUT" and task_id:
            body = json.loads(event.get("body") or "{}")

            new_status = body.get("status")
            if not new_status:
                return {
                    "statusCode": 400,
                    "body": json.dumps({"message": "Field 'status' is required"})
                }

            result = table.update_item(
                Key={"id": task_id},
                UpdateExpression="SET #s = :status, updated_at = :updated_at",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":status": new_status,
                    ":updated_at": datetime.now().isoformat()
                },
                ReturnValues="ALL_NEW"
            )
            updated_task = result.get("Attributes", {})
            write_audit_log("UPDATE_TASK_STATUS", {"id": task_id, "new_status": new_status})

            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"message": "Task updated", "task": updated_task})
            }

        # GET /tasks?status=open — отримання списку з фільтрацією
        elif http_method == "GET" and path.startswith("/tasks"):
            status_filter = query_params.get("status")

            if status_filter:
                response = table.scan(
                    FilterExpression="attribute_exists(id) AND #s = :status",
                    ExpressionAttributeNames={"#s": "status"},
                    ExpressionAttributeValues={":status": status_filter}
                )
            else:
                response = table.scan()

            tasks = response.get("Items", [])

            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"tasks": tasks})
            }

        return {
            "statusCode": 405,
            "body": json.dumps({"message": "Method Not Allowed"})
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"message": "Internal Server Error"})
        }