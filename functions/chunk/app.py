import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", 1000))
CHUNK_OVERLAP = int(os.environ.get("CHUNK_OVERLAP", 200))


def handler(event, context):
    text = event["text"]
    document = event["document"]

    words = text.split()
    chunks = []

    for i in range(0, len(words), CHUNK_SIZE - CHUNK_OVERLAP):
        chunk = " ".join(words[i:i + CHUNK_SIZE])
        if chunk.strip():
            chunks.append(chunk)

    logger.info(f"Split into {len(chunks)} chunks")

    return {
        "chunks": chunks,
        "document": document,
        "bucket": event["bucket"]
    }
