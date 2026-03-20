import boto3
import os
import uuid
import logging
from botocore.exceptions import ClientError, BotoCoreError

logger = logging.getLogger(__name__)

AWS_BUCKET = os.getenv("AWS_S3_BUCKET_NAME")

s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION"),
)


# -----------------------------
# SINGLE UPLOAD
# -----------------------------
def generate_aws_upload_url(user_id, file_name, file_type):

    try:

        key = f"users/{user_id}/{uuid.uuid4()}_{file_name}"

        url = s3.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": AWS_BUCKET,
                "Key": key,
                "ContentType": file_type,
            },
            ExpiresIn=3600,
        )

        return key, url

    except (ClientError, BotoCoreError) as e:

        logger.error(f"AWS upload url error: {str(e)}")

        raise RuntimeError("AWS upload URL generation failed")


# -----------------------------
# DOWNLOAD
# -----------------------------
def generate_aws_download_url(object_key):

    try:

        return s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": AWS_BUCKET, "Key": object_key},
            ExpiresIn=3600,
        )

    except (ClientError, BotoCoreError) as e:

        logger.error(f"AWS download error: {str(e)}")

        raise RuntimeError("AWS download URL generation failed")


# -----------------------------
# DELETE
# -----------------------------
def delete_file_from_s3(object_key):

    try:

        s3.delete_object(
            Bucket=AWS_BUCKET,
            Key=object_key
        )

    except (ClientError, BotoCoreError) as e:

        logger.error(f"AWS delete error: {str(e)}")

        raise RuntimeError("AWS delete failed")


# -----------------------------
# MULTIPART START
# -----------------------------
def start_multipart_upload(user_id, file_name, file_type):

    try:

        key = f"users/{user_id}/{uuid.uuid4()}_{file_name}"

        response = s3.create_multipart_upload(
            Bucket=AWS_BUCKET,
            Key=key,
            ContentType=file_type
        )

        return key, response["UploadId"]

    except Exception as e:

        logger.error(f"AWS multipart start error: {str(e)}")

        raise RuntimeError("AWS multipart start failed")


# -----------------------------
# PART URL
# -----------------------------
def generate_part_upload_url(key, upload_id, part_number):

    try:

        url = s3.generate_presigned_url(
            "upload_part",
            Params={
                "Bucket": AWS_BUCKET,
                "Key": key,
                "UploadId": upload_id,
                "PartNumber": part_number,
            },
            ExpiresIn=3600,
        )

        return url

    except Exception as e:

        logger.error(f"AWS part URL error: {str(e)}")

        raise RuntimeError("AWS multipart part url failed")


# -----------------------------
# COMPLETE
# -----------------------------
def complete_multipart_upload(key, upload_id, parts):

    try:

        s3.complete_multipart_upload(
            Bucket=AWS_BUCKET,
            Key=key,
            UploadId=upload_id,
            MultipartUpload={"Parts": parts}
        )

    except Exception as e:

        logger.error(f"AWS multipart complete error: {str(e)}")

        raise RuntimeError("AWS multipart completion failed")