from __future__ import annotations

import json

from src.services.embedding import EmbeddingService
from src.services.qdrant import QdrantService
from src.services.s3 import S3Service


def lambda_handler(event, context):
    s3_service = S3Service()
    embedding_service = EmbeddingService()
    qdrant_service = QdrantService()

    indexed = []

    for record in event.get("Records", []):
        if record.get("eventSource") == "aws:sqs":
            body = json.loads(record["body"])
            records = body.get("Records", [])
        else:
            records = [record]

        for item in records:
            bucket, key = s3_service.parse_event_record(item)
            source_uri = s3_service.build_s3_uri(bucket, key)
            text, metadata = s3_service.read_document(bucket, key)
            title = s3_service.infer_title(key)

            chunks = embedding_service.chunk_text(text)
            if not chunks:
                indexed.append({
                    "bucket": bucket,
                    "key": key,
                    "status": "skipped_empty",
                })
                continue

            vectors = embedding_service.embed_texts(chunks)
            doc_id, points = qdrant_service.build_points(
                full_text=text,
                chunks=chunks,
                vectors=vectors,
                source="s3",
                title=title,
                url_or_file_path=source_uri,
                tags=["s3", "async-indexed"],
                section_prefix=title.replace(".", "_"),
            )
            qdrant_service.upsert_points(points)

            indexed.append({
                "bucket": bucket,
                "key": key,
                "doc_id": doc_id,
                "chunks_indexed": len(points),
                "metadata": metadata,
                "status": "indexed",
            })

    return {
        "statusCode": 200,
        "body": json.dumps({"indexed": indexed}, default=str),
    }