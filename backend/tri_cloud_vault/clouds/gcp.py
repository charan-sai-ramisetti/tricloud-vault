from google.cloud import storage
import os
import uuid
from datetime import timedelta

client = storage.Client()
bucket = client.bucket(os.getenv("GCP_BUCKET_NAME"))


def generate_gcp_upload_url(user_id, file_name):
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
    blob = bucket.blob(blob_name)
    return blob.generate_signed_url(
        version="v4",
        expiration=timedelta(hours=1),
        method="GET",
    )

def delete_file_from_gcp(blob_name):
    blob = bucket.blob(blob_name)
    blob.delete()
