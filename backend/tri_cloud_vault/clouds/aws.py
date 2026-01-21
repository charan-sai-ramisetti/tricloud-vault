import os
import uuid
import boto3
from botocore.exceptions import ClientError

AWS_BUCKET = os.getenv("AWS_S3_BUCKET_NAME")
AWS_REGION = os.getenv("AWS_REGION")

s3_client = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=AWS_REGION,
)


def upload_file_to_s3(file_obj, user_id):
    """
    Uploads file to S3 and returns the S3 object key
    """
    file_extension = os.path.splitext(file_obj.name)[1]
    object_key = f"users/{user_id}/{uuid.uuid4()}{file_extension}"

    try:
        s3_client.upload_fileobj(
            Fileobj=file_obj,
            Bucket=AWS_BUCKET,
            Key=object_key,
        )
    except ClientError as e:
        raise Exception(f"S3 upload failed: {str(e)}")

    return object_key

def download_file_from_s3(object_key):
    try:
        response = s3_client.get_object(
            Bucket=AWS_BUCKET,
            Key=object_key
        )
        return response["Body"]
    except ClientError as e:
        raise Exception(f"S3 download failed: {str(e)}")
    
    
def delete_file_from_s3(object_key):
    try:
        s3_client.delete_object(
            Bucket=AWS_BUCKET,
            Key=object_key
        )
    except ClientError as e:
        raise Exception(f"S3 delete failed: {str(e)}")


