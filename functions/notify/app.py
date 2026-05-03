import boto3
import json
import os
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

sns = boto3.client("sns")
SNS_TOPIC_ARN = os.environ["SNS_TOPIC_ARN"]


def handler(event, context):
    logger.info(f"Sending notification: {json.dumps(event)}")

    document = event.get("document", "unknown")
    indexed = event.get("indexed", 0)

    message = (
        f"RAG Pipeline Complete\n"
        f"Document: {document}\n"
        f"Chunks indexed: {indexed}"
    )

    sns.publish(
        TopicArn=SNS_TOPIC_ARN,
        Subject="RAG Pipeline Complete",
        Message=message
    )

    logger.info("Notification sent")

    return {
        "status": "notified",
        "document": document
    }
