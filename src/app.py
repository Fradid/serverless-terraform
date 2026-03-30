import json
import boto3
import os
import uuid
from datetime import datetime

TABLE_NAME = os.environ.get("TABLE_NAME")
if not TABLE_NAME:
    raise ValueError("TABLE_NAME environment variable is not set")

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)

def handler(event, context):
    try:
        http_method = event["requestContext"]["httpMethod"]

        if http_method == "POST":
            body = json.loads(event.get("body") or "{}")
            item_id = str(uuid.uuid4())
            item = {
                "id": item_id,
                "content": body.get("content", "Default"),
                "created_at": datetime.now().isoformat()
            }
            table.put_item(Item=item)
            return {
                "statusCode": 201,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"message": "Created", "item": item})
            }

        elif http_method == "GET":
            response = table.scan()
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"items": response["Items"]})
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