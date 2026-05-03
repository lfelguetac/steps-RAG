import boto3
import json
import os
import logging
from decimal import Decimal
import numpy as np

logger = logging.getLogger()
logger.setLevel(logging.INFO)

bedrock = boto3.client("bedrock-runtime")
dynamodb = boto3.resource("dynamodb")

EMBED_MODEL = os.environ.get("EMBED_MODEL", "amazon.titan-embed-text-v2:0")
LLM_MODEL = os.environ.get("LLM_MODEL", "anthropic.claude-3-haiku-20240307-v1:0")
TABLE_NAME = os.environ["TABLE_NAME"]
TOP_K = int(os.environ.get("TOP_K", 5))


def get_embedding(text):
    resp = bedrock.invoke_model(
        modelId=EMBED_MODEL,
        body=json.dumps({"inputText": text})
    )
    return json.loads(resp["body"].read())["embedding"]


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

    llm_resp = bedrock.invoke_model(
        modelId=LLM_MODEL,
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}]
        })
    )
    llm_body = json.loads(llm_resp["body"].read())
    answer = llm_body["content"][0]["text"]

    return {
        "statusCode": 200,
        "body": json.dumps({
            "answer": answer,
            "sources": [{"text": c["text"][:200], "score": round(c["score"], 4)} for c in top_chunks]
        })
    }
