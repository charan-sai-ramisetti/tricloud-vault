import os
import uuid
from google.cloud import storage

GCP_BUCKET = os.getenv("GCP_BUCKET_NAME")

client = storage.Client()
bucket = client.bucket(GCP_BUCKET)


def upload_file_to_gcp(file_obj, user_id):
    file_ext = os.path.splitext(file_obj.name)[1]
    blob_name = f"users/{user_id}/{uuid.uuid4()}{file_ext}"

    blob = bucket.blob(blob_name)
    blob.upload_from_file(file_obj)

    return blob_name


def download_file_from_gcp(blob_name):
    blob = bucket.blob(blob_name)
    return blob.open("rb")


def delete_file_from_gcp(blob_name):
    blob = bucket.blob(blob_name)
    blob.delete()
