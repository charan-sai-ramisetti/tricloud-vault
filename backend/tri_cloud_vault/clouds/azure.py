import os
import uuid
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import AzureError

AZURE_ACCOUNT_NAME = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
AZURE_ACCOUNT_KEY = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")
AZURE_CONTAINER = os.getenv("AZURE_CONTAINER_NAME")

connection_string = (
    f"DefaultEndpointsProtocol=https;"
    f"AccountName={AZURE_ACCOUNT_NAME};"
    f"AccountKey={AZURE_ACCOUNT_KEY};"
    f"EndpointSuffix=core.windows.net"
)

blob_service_client = BlobServiceClient.from_connection_string(connection_string)


def upload_file_to_azure(file_obj, user_id):
    """
    Upload file to Azure Blob Storage and return blob path
    """
    file_extension = os.path.splitext(file_obj.name)[1]
    blob_name = f"users/{user_id}/{uuid.uuid4()}{file_extension}"

    try:
        blob_client = blob_service_client.get_blob_client(
            container=AZURE_CONTAINER,
            blob=blob_name,
        )
        blob_client.upload_blob(file_obj, overwrite=True)
    except AzureError as e:
        raise Exception(f"Azure upload failed: {str(e)}")

    return blob_name

def download_file_from_azure(blob_name):
    blob_client = blob_service_client.get_blob_client(
        container=AZURE_CONTAINER,
        blob=blob_name
    )
    stream = blob_client.download_blob()
    return stream.chunks()

def delete_file_from_azure(blob_name):
    blob_client = blob_service_client.get_blob_client(
        container=AZURE_CONTAINER,
        blob=blob_name
    )
    blob_client.delete_blob()

