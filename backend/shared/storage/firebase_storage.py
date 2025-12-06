"""Firebase Storage helper utilities."""
from __future__ import annotations

import logging
from typing import Optional, Tuple

from firebase_admin import storage

from shared.auth.firebase_auth import initialize_firebase
from shared.config.settings import settings

logger = logging.getLogger(__name__)

# Ensure Firebase app is initialized before accessing storage.
initialize_firebase()


def _parse_storage_path(storage_path: str) -> Tuple[Optional[str], str]:
    """
    Parse a storage path and return (bucket_name, blob_name).

    Supports:
    - gs://bucket/path/to/blob
    - bucket/path/to/blob
    - path/to/blob (uses default bucket)
    """
    if storage_path.startswith("gs://"):
        path = storage_path[5:]
        parts = path.split("/", 1)
        bucket_name = parts[0]
        blob_name = parts[1] if len(parts) > 1 else ""
        return bucket_name, blob_name

    # Allow specifying bucket explicitly (`bucket_name/path`)
    if storage_path.count("/") > 0 and storage_path.split("/", 1)[0].endswith(".appspot.com"):
        bucket_name, blob_name = storage_path.split("/", 1)
        return bucket_name, blob_name

    # Otherwise, use default bucket
    return None, storage_path


def download_blob_as_bytes(storage_path: str) -> bytes:
    """
    Download a file from Firebase Storage as bytes.

    Args:
        storage_path: Path to the blob. Accepts gs:// URLs or relative paths.

    Returns:
        Blob contents as bytes.
    """
    if not storage_path:
        raise ValueError("storage_path is required")

    bucket_name_override, blob_name = _parse_storage_path(storage_path)
    
    # Use default bucket from Firebase app if no bucket specified
    try:
        if bucket_name_override:
            bucket = storage.bucket(bucket_name_override)
        else:
            # Use default bucket from Firebase app
            bucket = storage.bucket()
            bucket_name_override = bucket.name
    except Exception as e:
        logger.error(f"Error accessing Firebase Storage bucket: {e}")
        raise ValueError(
            f"Failed to access Firebase Storage bucket. "
            f"Make sure Firebase Storage is enabled and the bucket exists. Error: {e}"
        )

    blob = bucket.blob(blob_name.lstrip("/"))

    if not blob.exists():
        raise FileNotFoundError(
            f"Blob '{blob_name}' does not exist in bucket '{bucket_name_override}'."
        )

    logger.debug(f"Downloading blob '{blob_name}' from bucket '{bucket_name_override}'")
    return blob.download_as_bytes()


def upload_blob_from_bytes(
    storage_path: str,
    file_bytes: bytes,
    content_type: str = "application/octet-stream"
) -> str:
    """
    Upload bytes to Firebase Storage.

    Args:
        storage_path: Path where the blob should be stored (relative to bucket).
        file_bytes: File contents as bytes.
        content_type: MIME type of the file.

    Returns:
        Full storage path (gs://bucket/path).
    """
    if not storage_path:
        raise ValueError("storage_path is required")

    bucket_name_override, blob_name = _parse_storage_path(storage_path)
    
    # Use default bucket from Firebase app if no bucket specified
    # This uses the storageBucket from Firebase app initialization
    try:
        if bucket_name_override:
            bucket = storage.bucket(bucket_name_override)
        else:
            # Use default bucket from Firebase app
            bucket = storage.bucket()
            bucket_name_override = bucket.name
    except Exception as e:
        logger.error(f"Error accessing Firebase Storage bucket: {e}")
        raise ValueError(
            f"Failed to access Firebase Storage bucket. "
            f"Make sure Firebase Storage is enabled and the bucket exists. Error: {e}"
        )

    blob = bucket.blob(blob_name.lstrip("/"))
    blob.content_type = content_type

    logger.debug(f"Uploading blob '{blob_name}' to bucket '{bucket_name_override}' (size: {len(file_bytes)} bytes)")
    try:
        blob.upload_from_string(file_bytes, content_type=content_type)
    except Exception as e:
        logger.error(f"Failed to upload blob to Firebase Storage: {e}")
        raise ValueError(
            f"Failed to upload file to Firebase Storage. "
            f"Make sure Firebase Storage is enabled and you have write permissions. Error: {e}"
        )

    # Return full gs:// path
    return f"gs://{bucket_name_override}/{blob_name.lstrip('/')}"


