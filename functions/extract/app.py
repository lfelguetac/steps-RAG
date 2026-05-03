import boto3
import json
import os
import logging
import io
import PyPDF2

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")


def handler(event, context):
    logger.info(f"Extracting text from {event}")

    bucket = event["bucket"]
    key = event["key"]

    resp = s3.get_object(Bucket=bucket, Key=key)
    data = resp["Body"].read()

    ext = key.split(".")[-1].lower()

    if ext == "pdf":
        reader = PyPDF2.PdfReader(io.BytesIO(data))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    else:
        text = data.decode("utf-8")

    text = text.strip()
    if not text:
        raise ValueError(f"No text extracted from {key}")

    logger.info(f"Extracted {len(text)} characters from {key}")

    return {
        "text": text,
        "document": key,
        "bucket": bucket
    }
