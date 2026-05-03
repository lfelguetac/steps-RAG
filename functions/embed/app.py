import requests
import json
import os
import logging
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")
HF_API_KEY = os.environ["HF_API_KEY"]
HF_MODEL = os.environ.get("HF_EMBED_MODEL", "BAAI/bge-base-en-v1.5")
HF_API_URL = f"https://router.huggingface.co/hf-inference/models/{HF_MODEL}?pipeline=feature-extraction"
EMBEDDINGS_BUCKET = os.environ.get("UPLOAD_BUCKET", "")


def get_embedding(text):
    response = requests.post(
        HF_API_URL,
        headers={"Authorization": f"Bearer {HF_API_KEY}"},
        json={"inputs": text}
    )
    if response.status_code != 200:
        raise Exception(f"HF API error: {response.status_code} - {response.text}")
    result = response.json()
    if isinstance(result, list) and len(result) > 0 and isinstance(result[0], (int, float)):
        return result
    if isinstance(result, list) and len(result) > 0 and isinstance(result[0], list):
        return result[0]
    raise Exception(f"Unexpected HF response: {result}")


def handler(event, context):
    chunks = event["chunks"]
    document = event["document"]
    bucket = event["bucket"]

    embeddings = []
    for i, chunk in enumerate(chunks):
        embedding = get_embedding(chunk)
        embeddings.append({
            "chunk_id": f"{document}_{i}",
            "embedding": embedding,
            "text": chunk
        })
        logger.info(f"Embedded chunk {i+1}/{len(chunks)}")

    s3_key = f"embeddings/{document}.json"
    if EMBEDDINGS_BUCKET:
        s3.put_object(Bucket=EMBEDDINGS_BUCKET, Key=s3_key, Body=json.dumps(embeddings))
        logger.info(f"Saved embeddings to s3://{EMBEDDINGS_BUCKET}/{s3_key}")

    return {
        "embeddings_s3_bucket": EMBEDDINGS_BUCKET,
        "embeddings_s3_key": s3_key,
        "document": document,
        "bucket": bucket,
        "chunk_count": len(embeddings)
    }
