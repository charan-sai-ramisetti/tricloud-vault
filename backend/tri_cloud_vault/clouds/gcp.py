from google.cloud import storage
from google.api_core.exceptions import GoogleAPIError
from datetime import timedelta
import os
import uuid
import logging

logger = logging.getLogger(__name__)

client = storage.Client()

bucket = client.bucket(os.getenv("GCP_BUCKET_NAME"))


# -----------------------------
# SINGLE UPLOAD
# -----------------------------
def generate_gcp_upload_url(user_id, file_name):

    try:

        blob_name = f"users/{user_id}/{uuid.uuid4()}_{file_name}"

        blob = bucket.blob(blob_name)

        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=15),
            method="PUT",
            content_type="application/octet-stream"
        )

        return blob_name, url

    except GoogleAPIError as e:

        logger.error(str(e))

        raise RuntimeError("GCP upload url generation failed")


# -----------------------------
# DOWNLOAD
# -----------------------------
def generate_gcp_download_url(blob_name):

    try:

        blob = bucket.blob(blob_name)

        return blob.generate_signed_url(
            version="v4",
            expiration=timedelta(hours=1),
            method="GET"
        )

    except GoogleAPIError as e:

        logger.error(str(e))

        raise RuntimeError("GCP download url generation failed")


# -----------------------------
# DELETE
# -----------------------------
def delete_file_from_gcp(blob_name):

    try:

        blob = bucket.blob(blob_name)

        blob.delete()

    except GoogleAPIError as e:

        logger.error(str(e))

        raise RuntimeError("GCP delete failed")


# -----------------------------
# RESUMABLE UPLOAD
# -----------------------------
def start_resumable_upload(user_id, file_name, file_type):

    try:

        blob_name = f"users/{user_id}/{uuid.uuid4()}_{file_name}"

        blob = bucket.blob(blob_name)

        session = blob.create_resumable_upload_session(
            content_type=file_type
        )

        return blob_name, session

    except GoogleAPIError as e:

        logger.error(str(e))

        raise RuntimeError("GCP resumable upload start failed")