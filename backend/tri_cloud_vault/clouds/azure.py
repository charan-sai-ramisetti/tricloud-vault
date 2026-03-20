from azure.storage.blob import (
    BlobServiceClient,
    generate_blob_sas,
    BlobSasPermissions,
)
from azure.core.exceptions import AzureError
from datetime import datetime, timedelta
import os
import uuid
import logging

logger = logging.getLogger(__name__)

ACCOUNT_NAME = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
ACCOUNT_KEY = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")
CONTAINER = os.getenv("AZURE_CONTAINER_NAME")

service = BlobServiceClient(
    account_url=f"https://{ACCOUNT_NAME}.blob.core.windows.net",
    credential=ACCOUNT_KEY,
)


# -----------------------------
# SINGLE UPLOAD
# -----------------------------
def generate_azure_upload_url(user_id, file_name):

    try:

        blob_name = f"users/{user_id}/{uuid.uuid4()}_{file_name}"

        sas = generate_blob_sas(
            account_name=ACCOUNT_NAME,
            container_name=CONTAINER,
            blob_name=blob_name,
            account_key=ACCOUNT_KEY,
            permission=BlobSasPermissions(write=True),
            expiry=datetime.utcnow() + timedelta(hours=1),
        )

        url = f"https://{ACCOUNT_NAME}.blob.core.windows.net/{CONTAINER}/{blob_name}?{sas}"

        return blob_name, url

    except AzureError as e:

        logger.error(str(e))

        raise RuntimeError("Azure upload url generation failed")


# -----------------------------
# DOWNLOAD
# -----------------------------
def generate_azure_download_url(blob_name):

    try:

        sas = generate_blob_sas(
            account_name=ACCOUNT_NAME,
            container_name=CONTAINER,
            blob_name=blob_name,
            account_key=ACCOUNT_KEY,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(hours=1),
        )

        return f"https://{ACCOUNT_NAME}.blob.core.windows.net/{CONTAINER}/{blob_name}?{sas}"

    except AzureError as e:

        logger.error(str(e))

        raise RuntimeError("Azure download failed")


# -----------------------------
# DELETE
# -----------------------------
def delete_file_from_azure(blob_name):

    try:

        blob_client = service.get_blob_client(
            container=CONTAINER,
            blob=blob_name
        )

        blob_client.delete_blob()

    except AzureError as e:

        logger.error(str(e))

        raise RuntimeError("Azure delete failed")


# -----------------------------
# BLOCK UPLOAD
# -----------------------------
def generate_block_upload_url(blob_name, block_id):

    try:

        sas = generate_blob_sas(
            account_name=ACCOUNT_NAME,
            container_name=CONTAINER,
            blob_name=blob_name,
            account_key=ACCOUNT_KEY,
            permission=BlobSasPermissions(write=True),
            expiry=datetime.utcnow() + timedelta(hours=1),
        )

        return f"https://{ACCOUNT_NAME}.blob.core.windows.net/{CONTAINER}/{blob_name}?comp=block&blockid={block_id}&{sas}"

    except AzureError as e:

        logger.error(str(e))

        raise RuntimeError("Azure block upload url failed")


def commit_block_list(blob_name, block_ids):

    try:

        blob = service.get_blob_client(CONTAINER, blob_name)

        blob.commit_block_list(block_ids)

    except AzureError as e:

        logger.error(str(e))

        raise RuntimeError("Azure block commit failed")