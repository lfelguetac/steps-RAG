import boto3
import requests
import json
import os
import logging
from decimal import Decimal
import numpy as np

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")

HF_API_KEY = os.environ["HF_API_KEY"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]
HF_MODEL = os.environ.get("HF_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")
HF_API_URL = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{HF_MODEL}"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
TABLE_NAME = os.environ["TABLE_NAME"]
TOP_K = int(os.environ.get("TOP_K", 5))


def get_embedding(text):
    resp = requests.post(
        HF_API_URL,
        headers={"Authorization": f"Bearer {HF_API_KEY}"},
        json={"inputs": text, "options": {"wait_for_model": True}}
    )
    if resp.status_code != 200:
        raise Exception(f"HF API error: {resp.status_code} - {resp.text}")
    result = resp.json()
    if isinstance(result, list) and len(result) > 0 and isinstance(result[0], (int, float)):
        return result
    if isinstance(result, list) and len(result) > 0 and isinstance(result[0], list):
        return result[0]
    raise Exception(f"Unexpected HF response: {result}")


def cosine_similarity(a, b):
    a = np.array(a, dtype=float)
    b = np.array(b, dtype=float)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def handler(event, context):
    logger.info(f"Query event: {event}")

    body = json.loads(event.get("body", "{}")) if isinstance(event.get("body"), str) else event
    question = body.get("question", "")

    if not question:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "question is required"})
        }

    query_embedding = get_embedding(question)

    table = dynamodb.Table(TABLE_NAME)
    response = table.scan()
    items = response["Items"]
    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items.extend(response["Items"])

    scored = []
    for item in items:
        embedding = [float(v) for v in item["embedding"]]
        score = cosine_similarity(query_embedding, embedding)
        scored.append({"text": item["text"], "score": score, "document": item["document"]})

    scored.sort(key=lambda x: x["score"], reverse=True)
    top_chunks = scored[:TOP_K]

    context_text = "\n\n".join(c["text"] for c in top_chunks)

    prompt = f"""Answer the following question based on the provided context. If the context doesn't contain relevant information, say so.

Context:
{context_text}

Question: {question}

Answer:"""

    groq_resp = requests.post(
        GROQ_API_URL,
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": GROQ_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1024
        }
    )
    if groq_resp.status_code != 200:
        raise Exception(f"Groq API error: {groq_resp.status_code} - {groq_resp.text}")

    groq_body = groq_resp.json()
    answer = groq_body["choices"][0]["message"]["content"]

    return {
        "statusCode": 200,
        "body": json.dumps({
            "answer": answer,
            "sources": [{"text": c["text"][:200], "score": round(c["score"], 4)} for c in top_chunks]
        })
    }
