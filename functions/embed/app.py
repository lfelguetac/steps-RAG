import boto3
import json
import os
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

bedrock = boto3.client("bedrock-runtime")
MODEL_ID = os.environ.get("EMBED_MODEL", "amazon.titan-embed-text-v2:0")


def handler(event, context):
    chunks = event["chunks"]
    document = event["document"]

    embeddings = []
    for i, chunk in enumerate(chunks):
        body = json.dumps({"inputText": chunk})
        resp = bedrock.invoke_model(
            modelId=MODEL_ID,
            body=body
        )
        resp_body = json.loads(resp["body"].read())
        embedding = resp_body["embedding"]
        embeddings.append({
            "chunk_id": f"{document}_{i}",
            "embedding": embedding,
            "text": chunk
        })
        logger.info(f"Embedded chunk {i+1}/{len(chunks)}")

    return {
        "embeddings": embeddings,
        "document": document,
        "bucket": event["bucket"]
    }
