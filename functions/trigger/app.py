import boto3
import json
import os
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

sfn = boto3.client("stepfunctions")
STATE_MACHINE_ARN = os.environ["STATE_MACHINE_ARN"]


def handler(event, context):
    logger.info(f"Received event: {json.dumps(event)}")

    bucket = event.get("bucket", os.environ.get("UPLOAD_BUCKET"))
    key = event.get("key", "")

    if not bucket or not key:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "bucket and key are required"})
        }

    response = sfn.start_execution(
        stateMachineArn=STATE_MACHINE_ARN,
        input=json.dumps({"bucket": bucket, "key": key})
    )

    return {
        "statusCode": 200,
        "body": json.dumps({
            "status": "processing",
            "execution_arn": response["executionArn"],
            "document": key
        })
    }
