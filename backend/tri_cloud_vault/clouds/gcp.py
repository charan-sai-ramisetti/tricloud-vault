from google.cloud import storage
import os
import uuid
from datetime import timedelta

# Initialize client once
client = storage.Client()
bucket = client.bucket(os.getenv("GCP_BUCKET_NAME"))


# ================================
# Generate Upload URL
# ================================
def generate_gcp_upload_url(user_id, file_name):
    blob_name = f"users/{user_id}/{uuid.uuid4()}_{file_name}"
    blob = bucket.blob(blob_name)

    upload_url = blob.generate_signed_url(
        version="v4",
        expiration=timedelta(minutes=15),
        method="PUT",
        content_type="application/octet-stream"
    )

    return blob_name, upload_url


# ================================
# Generate Download URL
# ================================
def generate_gcp_download_url(blob_name):
    blob = bucket.blob(blob_name)

    return blob.generate_signed_url(
        version="v4",
        expiration=timedelta(hours=1),
        method="GET"
    )


# ================================
# Delete File
# ================================
def delete_file_from_gcp(blob_name):
    blob = bucket.blob(blob_name)
    blob.delete()
