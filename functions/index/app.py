import boto3
import json
import os
import logging
from decimal import Decimal

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")
TABLE_NAME = os.environ["TABLE_NAME"]
table = dynamodb.Table(TABLE_NAME)


def float_to_decimal(obj):
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, list):
        return [float_to_decimal(i) for i in obj]
    return obj


def handler(event, context):
    s3_bucket = event["embeddings_s3_bucket"]
    s3_key = event["embeddings_s3_key"]
    document = event["document"]
    bucket = event["bucket"]

    response = s3.get_object(Bucket=s3_bucket, Key=s3_key)
    embeddings = json.loads(response["Body"].read())

    with table.batch_writer() as batch:
        for emb in embeddings:
            item = {
                "document": document,
                "chunk_id": emb["chunk_id"],
                "embedding": float_to_decimal(emb["embedding"]),
                "text": emb["text"]
            }
            batch.put_item(Item=item)

    logger.info(f"Indexed {len(embeddings)} embeddings for {document}")

    return {
        "indexed": len(embeddings),
        "document": document,
        "bucket": bucket
    }
