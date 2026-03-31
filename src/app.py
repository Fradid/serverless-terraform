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
        http_method = event["requestContext"]["httpMethod"]
        path = event.get("path", "")
        path_params = event.get("pathParameters") or {}
        query_params = event.get("queryStringParameters") or {}

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
                "priority": body.get("priority", "medium"),  # low / medium / high
                "status": body.get("status", "open"),        # open / in_progress / done
                "created_at": datetime.now().isoformat()
            }
            table.put_item(Item=task)
            write_audit_log("CREATE_TASK", task)

            return {
                "statusCode": 201,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"message": "Task created", "task": task})
            }

        # PUT /tasks/{id} — оновлення статусу
        elif http_method == "PUT" and path_params.get("id"):
            task_id = path_params["id"]
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
        elif http_method == "GET" and path == "/tasks":
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