import base64
from azure.storage.blob import (
    BlobServiceClient,
    BlobBlock,
    generate_blob_sas,
    BlobSasPermissions,
)
from azure.core.exceptions import AzureError
from datetime import datetime, timedelta
import os
import uuid
import urllib.parse
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

        # URL-encode the block_id for the query string
        encoded_block_id = urllib.parse.quote(block_id, safe='')

        sas = generate_blob_sas(
            account_name=ACCOUNT_NAME,
            container_name=CONTAINER,
            blob_name=blob_name,
            account_key=ACCOUNT_KEY,
            permission=BlobSasPermissions(write=True),
            expiry=datetime.utcnow() + timedelta(hours=1),
        )

        return f"https://{ACCOUNT_NAME}.blob.core.windows.net/{CONTAINER}/{blob_name}?comp=block&blockid={encoded_block_id}&{sas}"

    except AzureError as e:

        logger.error(str(e))

        raise RuntimeError("Azure block upload url failed")


# -----------------------------
# COMMIT BLOCK LIST
# -----------------------------
def commit_block_list(blob_name, block_ids):

    try:

        logger.info(f"Committing blocks for {blob_name}: {block_ids}")

        blob = service.get_blob_client(CONTAINER, blob_name)

        # block_ids arrive as base64 strings (e.g. "MDAwMDAx") from the frontend.
        # The Azure SDK's BlobBlock() internally base64-encodes whatever string you
        # pass to it, so we must pass the DECODED plain string (e.g. "000001") so
        # the SDK re-encodes it to the same ID that was used during the block upload.
        # Passing the raw base64 causes double-encoding → InvalidBlobOrBlock error.
        blocks = [
            BlobBlock(block_id=base64.b64decode(block_id).decode())
            for block_id in block_ids
        ]

        blob.commit_block_list(blocks)

    except AzureError as e:

        logger.error(str(e))

        raise RuntimeError("Azure block commit failed")