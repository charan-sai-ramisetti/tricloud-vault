from google.cloud import storage
from google.auth.exceptions import DefaultCredentialsError
import os
import uuid
from datetime import timedelta


def is_gcp_enabled():
    return bool(
        os.getenv("GOOGLE_APPLICATION_CREDENTIALS") and
        os.getenv("GCP_BUCKET_NAME")
    )


def get_gcp_bucket():
    if not is_gcp_enabled():
        return None

    try:
        client = storage.Client()
        return client.bucket(os.getenv("GCP_BUCKET_NAME"))
    except DefaultCredentialsError:
        return None


def generate_gcp_upload_url(user_id, file_name):
    bucket = get_gcp_bucket()
    if bucket is None:
        return None, None

    blob_name = f"users/{user_id}/{uuid.uuid4()}_{file_name}"
    blob = bucket.blob(blob_name)

    url = blob.generate_signed_url(
        version="v4",
        expiration=timedelta(hours=1),
        method="PUT",
        content_type="application/octet-stream",
    )

    return blob_name, url


def generate_gcp_download_url(blob_name):
    bucket = get_gcp_bucket()
    if bucket is None:
        return None

    blob = bucket.blob(blob_name)
    return blob.generate_signed_url(
        version="v4",
        expiration=timedelta(hours=1),
        method="GET",
    )


def delete_file_from_gcp(blob_name):
    bucket = get_gcp_bucket()
    if bucket is None:
        return False

    blob = bucket.blob(blob_name)
    blob.delete()
    return True
