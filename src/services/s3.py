from __future__ import annotations

from io import BytesIO
from typing import Any
from urllib.parse import unquote_plus

import boto3


class S3Service:
    def __init__(self) -> None:
        self.client = boto3.client("s3")

    def parse_event_record(self, record: dict[str, Any]) -> tuple[str, str]:
        bucket = record["s3"]["bucket"]["name"]
        key = unquote_plus(record["s3"]["object"]["key"])
        return bucket, key

    def build_s3_uri(self, bucket: str, key: str) -> str:
        return f"s3://{bucket}/{key}"

    def infer_title(self, key: str) -> str:
        return key.rsplit("/", 1)[-1]

    def read_document(self, bucket: str, key: str) -> tuple[str, dict[str, Any]]:
        obj = self.client.get_object(Bucket=bucket, Key=key)
        body = obj["Body"].read()
        content_type = obj.get("ContentType", "")

        metadata = {
            "content_type": content_type,
            "last_modified": obj.get("LastModified"),
            "etag": obj.get("ETag"),
        }

        if key.lower().endswith(".pdf") or content_type == "application/pdf":
            import pypdf

            reader = pypdf.PdfReader(BytesIO(body))
            pages = [page.extract_text() or "" for page in reader.pages]
            return "\n".join(pages), metadata

        return body.decode("utf-8", errors="ignore"), metadata