from google.cloud import storage
from google.api_core.exceptions import GoogleAPIError
import os
import uuid
from datetime import timedelta

client = storage.Client()
bucket = client.bucket(os.getenv("GCP_BUCKET_NAME"))


def generate_gcp_upload_url(user_id, file_name):
    try:
        blob_name = f"users/{user_id}/{uuid.uuid4()}_{file_name}"
        blob = bucket.blob(blob_name)

        upload_url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=15),
            method="PUT",
            content_type="application/octet-stream"
        )

        return blob_name, upload_url

    except GoogleAPIError as e:
        raise RuntimeError(f"GCP upload URL generation failed: {str(e)}")


def generate_gcp_download_url(blob_name):
    try:
        blob = bucket.blob(blob_name)

        return blob.generate_signed_url(
            version="v4",
            expiration=timedelta(hours=1),
            method="GET"
        )

    except GoogleAPIError as e:
        raise RuntimeError(f"GCP download URL generation failed: {str(e)}")


def delete_file_from_gcp(blob_name):
    try:
        blob = bucket.blob(blob_name)
        blob.delete()

    except GoogleAPIError as e:
        raise RuntimeError(f"GCP delete failed: {str(e)}")
