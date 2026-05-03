import requests
import json
import os
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

HF_API_KEY = os.environ["HF_API_KEY"]
HF_MODEL = os.environ.get("HF_EMBED_MODEL", "BAAI/bge-base-en-v1.5")
HF_API_URL = f"https://router.huggingface.co/hf-inference/models/{HF_MODEL}?pipeline=feature-extraction"


def get_embedding(text):
    response = requests.post(
        HF_API_URL,
        headers={"Authorization": f"Bearer {HF_API_KEY}"},
        json={"inputs": text, "options": {"wait_for_model": True}}
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

    embeddings = []
    for i, chunk in enumerate(chunks):
        embedding = get_embedding(chunk)
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
