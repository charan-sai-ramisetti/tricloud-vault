import boto3
import os
import uuid
from botocore.exceptions import ClientError, BotoCoreError

AWS_BUCKET = os.getenv("AWS_S3_BUCKET_NAME")

s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION"),
)


def generate_aws_upload_url(user_id, file_name,file_type):
    try:
        key = f"users/{user_id}/{uuid.uuid4()}_{file_name}"

        url = s3.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": AWS_BUCKET,
                "Key": key,
                "ContentType": file_type
            },
            ExpiresIn=3600,
        )

        return key, url

    except (ClientError, BotoCoreError) as e:
        raise RuntimeError(f"AWS upload URL generation failed: {str(e)}")


def generate_aws_download_url(object_key):
    try:
        return s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": AWS_BUCKET, "Key": object_key},
            ExpiresIn=3600,
        )
    except (ClientError, BotoCoreError) as e:
        raise RuntimeError(f"AWS download URL generation failed: {str(e)}")


def delete_file_from_s3(object_key):
    try:
        s3.delete_object(
            Bucket=AWS_BUCKET,
            Key=object_key
        )
    except (ClientError, BotoCoreError) as e:
        raise RuntimeError(f"AWS delete failed: {str(e)}")
