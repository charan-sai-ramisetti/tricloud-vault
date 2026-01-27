from azure.storage.blob import (
    BlobServiceClient,
    generate_blob_sas,
    BlobSasPermissions,
)
from datetime import datetime, timedelta
import os
import uuid

AZURE_CONTAINER = os.getenv("AZURE_CONTAINER_NAME")
ACCOUNT_NAME = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
ACCOUNT_KEY = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")

service = BlobServiceClient(
    account_url=f"https://{ACCOUNT_NAME}.blob.core.windows.net",
    credential=ACCOUNT_KEY,
)


def generate_azure_upload_url(user_id, file_name):
    blob_name = f"users/{user_id}/{uuid.uuid4()}_{file_name}"

    sas = generate_blob_sas(
        account_name=ACCOUNT_NAME,
        container_name=AZURE_CONTAINER,
        blob_name=blob_name,
        account_key=ACCOUNT_KEY,
        permission=BlobSasPermissions(write=True),
        expiry=datetime.utcnow() + timedelta(hours=1),
    )

    url = f"https://{ACCOUNT_NAME}.blob.core.windows.net/{AZURE_CONTAINER}/{blob_name}?{sas}"
    return blob_name, url


def generate_azure_download_url(blob_name):
    sas = generate_blob_sas(
        account_name=ACCOUNT_NAME,
        container_name=AZURE_CONTAINER,
        blob_name=blob_name,
        account_key=ACCOUNT_KEY,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.utcnow() + timedelta(hours=1),
    )

    return f"https://{ACCOUNT_NAME}.blob.core.windows.net/{AZURE_CONTAINER}/{blob_name}?{sas}"


def delete_file_from_azure(blob_name):
    blob_client = service.get_blob_client(
        container=AZURE_CONTAINER,
        blob=blob_name
    )
    blob_client.delete_blob()

