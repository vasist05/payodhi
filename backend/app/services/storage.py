"""
MinIO / S3-compatible object storage service.

Buckets
-------
  payodi-scenes    – raw satellite scene files (TIFF, NetCDF, …)
  payodi-dossiers  – generated legal dossier PDFs / ZIPs

Usage
-----
    from app.services.storage import storage

    # Upload a local file
    url = storage.upload_file("payodi-scenes", "sentinel/2025/scene01.tif", "/tmp/scene01.tif")

    # Upload raw bytes
    url = storage.upload_bytes("payodi-dossiers", "dossiers/v1/d-001.pdf", pdf_bytes, content_type="application/pdf")

    # Download to a local path
    storage.download_file("payodi-scenes", "sentinel/2025/scene01.tif", "/tmp/download.tif")

    # Download as bytes
    data = storage.download_bytes("payodi-dossiers", "dossiers/v1/d-001.pdf")

    # Generate a pre-signed URL (default 1 hour)
    url = storage.presigned_url("payodi-dossiers", "dossiers/v1/d-001.pdf")

    # Delete an object
    storage.delete_object("payodi-scenes", "sentinel/2025/scene01.tif")

    # List objects under a prefix
    objects = storage.list_objects("payodi-scenes", prefix="sentinel/2025/")
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import BinaryIO

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.config import settings

logger = logging.getLogger(__name__)

# ── known bucket names ──────────────────────────────────────────────────────
BUCKET_SCENES = "payodi-scenes"
BUCKET_DOSSIERS = "payodi-dossiers"
KNOWN_BUCKETS = (BUCKET_SCENES, BUCKET_DOSSIERS)


class StorageService:
    """
    Thin wrapper around boto3 S3 client configured for MinIO.

    The client is created lazily on first use so that import-time
    failures don't break the process if MinIO is offline during tests.
    """

    def __init__(self) -> None:
        self._client: boto3.client | None = None

    @property
    def client(self) -> boto3.client:
        if self._client is None:
            self._client = boto3.client(
                "s3",
                endpoint_url=f"http://{settings.minio_endpoint}",
                aws_access_key_id=settings.minio_access_key,
                aws_secret_access_key=settings.minio_secret_key,
                region_name="us-east-1",
                config=Config(
                    signature_version="s3v4",
                    connect_timeout=5,
                    retries={"max_attempts": 3, "mode": "standard"},
                ),
            )
        return self._client

    # ── bucket helpers ──────────────────────────────────────────────────────

    def ensure_buckets(self) -> None:
        """Create all required buckets if they don't already exist.

        Call this once at application startup or from a migration helper.
        """
        for bucket in KNOWN_BUCKETS:
            try:
                self.client.create_bucket(Bucket=bucket)
                logger.info("Created bucket: %s", bucket)
            except ClientError as exc:
                code = exc.response["Error"]["Code"]
                if code in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
                    logger.debug("Bucket already exists: %s", bucket)
                else:
                    raise

    # ── upload ──────────────────────────────────────────────────────────────

    def upload_file(
        self,
        bucket: str,
        key: str,
        local_path: str | Path,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> str:
        """Upload a local file. Returns the object key."""
        extra: dict = {"ContentType": content_type}
        if metadata:
            extra["Metadata"] = metadata
        self.client.upload_file(
            str(local_path),
            bucket,
            key,
            ExtraArgs=extra,
        )
        logger.info("Uploaded %s → s3://%s/%s", local_path, bucket, key)
        return key

    def upload_bytes(
        self,
        bucket: str,
        key: str,
        data: bytes | BinaryIO,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> str:
        """Upload raw bytes or a file-like object. Returns the object key."""
        body = data if isinstance(data, (bytes, bytearray)) else data.read()
        extra: dict = {"ContentType": content_type}
        if metadata:
            extra["Metadata"] = metadata
        self.client.put_object(
            Bucket=bucket,
            Key=key,
            Body=body,
            **extra,
        )
        logger.info("Uploaded bytes (%d B) → s3://%s/%s", len(body), bucket, key)
        return key

    # ── download ─────────────────────────────────────────────────────────────

    def download_file(
        self,
        bucket: str,
        key: str,
        local_path: str | Path,
    ) -> Path:
        """Download an object to a local file. Returns the resolved path."""
        path = Path(local_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.client.download_file(bucket, key, str(path))
        logger.info("Downloaded s3://%s/%s → %s", bucket, key, path)
        return path

    def download_bytes(self, bucket: str, key: str) -> bytes:
        """Download an object and return its raw bytes."""
        buf = io.BytesIO()
        self.client.download_fileobj(bucket, key, buf)
        buf.seek(0)
        data = buf.read()
        logger.info("Downloaded s3://%s/%s (%d B)", bucket, key, len(data))
        return data

    # ── presigned URL ─────────────────────────────────────────────────────────

    def presigned_url(
        self,
        bucket: str,
        key: str,
        expiry_seconds: int = 3600,
    ) -> str:
        """Return a pre-signed GET URL valid for *expiry_seconds* (default 1h)."""
        url = self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expiry_seconds,
        )
        return url

    # ── delete ────────────────────────────────────────────────────────────────

    def delete_object(self, bucket: str, key: str) -> None:
        """Delete a single object. No-op if the object does not exist."""
        self.client.delete_object(Bucket=bucket, Key=key)
        logger.info("Deleted s3://%s/%s", bucket, key)

    # ── list ──────────────────────────────────────────────────────────────────

    def list_objects(
        self,
        bucket: str,
        prefix: str = "",
        max_keys: int = 1000,
    ) -> list[dict]:
        """Return a list of object metadata dicts under *prefix*.

        Each dict has keys: Key, Size, LastModified, ETag.
        """
        resp = self.client.list_objects_v2(
            Bucket=bucket,
            Prefix=prefix,
            MaxKeys=max_keys,
        )
        contents = resp.get("Contents", [])
        return [
            {
                "key": obj["Key"],
                "size": obj["Size"],
                "last_modified": obj["LastModified"],
                "etag": obj["ETag"].strip('"'),
            }
            for obj in contents
        ]

    # ── object metadata ───────────────────────────────────────────────────────

    def object_exists(self, bucket: str, key: str) -> bool:
        """Return True if the object exists in the bucket."""
        try:
            self.client.head_object(Bucket=bucket, Key=key)
            return True
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "404":
                return False
            raise


# Module-level singleton — import and use directly.
storage = StorageService()
