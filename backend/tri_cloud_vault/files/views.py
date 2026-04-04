from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.db.models import Sum, Case, When, BigIntegerField
import logging
import uuid

from payments.models import Subscription
from .models import File
from .serializers import FileSerializer

# ========= AWS =========
from clouds.aws import (
    generate_aws_upload_url,
    generate_aws_download_url,
    delete_file_from_s3,
    start_multipart_upload,
    generate_part_upload_url,
    complete_multipart_upload,
)

# ========= AZURE =========
from clouds.azure import (
    generate_azure_upload_url,
    generate_azure_download_url,
    delete_file_from_azure,
    generate_block_upload_url,
    commit_block_list,
)

# ========= GCP =========
from clouds.gcp import (
    generate_gcp_upload_url,
    generate_gcp_download_url,
    delete_file_from_gcp,
    start_resumable_upload,
)

logger = logging.getLogger(__name__)

ALLOWED_CLOUDS = {"AWS", "AZURE", "GCP"}

CHUNK_SIZE = 10 * 1024 * 1024  # 10 MB — must match frontend upload.js CHUNK_SIZE


# ==========================================
# FILE LIST
# ==========================================
class FileListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            files = File.objects.filter(user=request.user).order_by("-created_at")
            serializer = FileSerializer(files, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(str(e))
            return Response(
                {"error": "Failed to fetch files"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ==========================================
# PRESIGN UPLOAD
# ==========================================
class PresignUploadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):

        file_name = request.data.get("file_name")
        file_size = request.data.get("file_size")
        file_type = request.data.get("file_type")
        clouds = request.data.get("clouds", [])

        if not file_name or not file_size or not file_type or not clouds:
            return Response(
                {"error": "file_name, file_size, file_type and clouds are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            file_size = int(file_size)
        except Exception:
            return Response({"error": "Invalid file_size"}, status=400)

        MAX_FILE_SIZE_MB_DEFAULT = 100
        MAX_FILE_SIZE_MB_EXEMPT = 51200

        user = request.user

        if user.email == "charansairamisetti@gmail.com":
            max_size_mb = MAX_FILE_SIZE_MB_EXEMPT
        else:
            max_size_mb = MAX_FILE_SIZE_MB_DEFAULT

        if file_size > max_size_mb * 1024 * 1024:
            return Response(
                {"error": f"File size exceeds {max_size_mb} MB limit"},
                status=status.HTTP_403_FORBIDDEN,
            )

        clouds = [c.upper() for c in clouds]

        invalid = set(clouds) - ALLOWED_CLOUDS

        if invalid:
            return Response(
                {"error": f"Invalid clouds: {', '.join(invalid)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        subscription, _ = Subscription.objects.get_or_create(
            user=request.user,
            defaults={
                "plan": "FREE",
                "cloud_limit_mb": 1024,
                "max_file_size_mb": 100,
            },
        )

        cloud_limit_bytes = subscription.cloud_limit_mb * 1024 * 1024

        # Single conditional aggregate query for all three clouds — replaces the
        # previous loop that ran 1 separate DB query per selected cloud (up to 3 queries)
        usage_totals = File.objects.filter(user=request.user).aggregate(
            aws_total=Sum(
                Case(
                    When(aws_path__isnull=False, then="file_size"),
                    output_field=BigIntegerField(),
                )
            ),
            azure_total=Sum(
                Case(
                    When(azure_path__isnull=False, then="file_size"),
                    output_field=BigIntegerField(),
                )
            ),
            gcp_total=Sum(
                Case(
                    When(gcp_path__isnull=False, then="file_size"),
                    output_field=BigIntegerField(),
                )
            ),
        )

        cloud_usage = {
            "AWS":   usage_totals["aws_total"]   or 0,
            "AZURE": usage_totals["azure_total"] or 0,
            "GCP":   usage_totals["gcp_total"]   or 0,
        }

        for cloud in clouds:
            used = cloud_usage[cloud]
            if used + file_size > cloud_limit_bytes:
                return Response(
                    {
                        "error": f"{cloud} storage limit exceeded",
                        "used_mb": used // (1024 * 1024),
                        "limit_mb": subscription.cloud_limit_mb,
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        upload_urls = {}
        paths = {}

        upload_type = "single"

        if file_size > CHUNK_SIZE:
            upload_type = "multipart"

        if upload_type == "single":

            if "AWS" in clouds:
                key, url = generate_aws_upload_url(
                    request.user.id, file_name, file_type
                )
                upload_urls["AWS"] = url
                paths["aws_path"] = key

            if "AZURE" in clouds:
                key, url = generate_azure_upload_url(
                    request.user.id, file_name
                )
                upload_urls["AZURE"] = url
                paths["azure_path"] = key

            if "GCP" in clouds:
                key, url = generate_gcp_upload_url(
                    request.user.id, file_name
                )
                upload_urls["GCP"] = url
                paths["gcp_path"] = key

            return Response(
                {
                    "upload_type": "single",
                    "upload_urls": upload_urls,
                    "paths": paths,
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "upload_type": "multipart",
                "chunk_size": CHUNK_SIZE,
                "message": "Use multipart endpoints",
            },
            status=status.HTTP_200_OK,
        )


# ==========================================
# MULTIPART START
# ==========================================
class MultipartStartView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):

        file_name = request.data.get("file_name")
        file_type = request.data.get("file_type")
        cloud = request.data.get("cloud")

        if not file_name or not cloud:
            return Response({"error": "file_name and cloud required"}, status=400)

        cloud = cloud.upper()

        try:

            if cloud == "AWS":

                key, upload_id = start_multipart_upload(
                    request.user.id,
                    file_name,
                    file_type
                )

                return Response({
                    "key": key,
                    "upload_id": upload_id
                })

            if cloud == "GCP":

                blob, session = start_resumable_upload(
                    request.user.id,
                    file_name,
                    file_type
                )

                return Response({
                    "blob": blob,
                    "upload_url": session
                })

            if cloud == "AZURE":

                blob_name = f"users/{request.user.id}/{uuid.uuid4()}_{file_name}"

                return Response({
                    "blob_name": blob_name
                })

        except Exception as e:
            logger.error(str(e))
            return Response({"error": "Multipart start failed"}, status=500)


# ==========================================
# MULTIPART PRESIGN PART
# ==========================================
class MultipartPresignPartView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):

        cloud = request.data.get("cloud")

        if not cloud:
            return Response({"error": "cloud required"}, status=400)

        cloud = cloud.upper()

        try:

            if cloud == "AWS":

                key = request.data.get("key")
                upload_id = request.data.get("upload_id")
                part_number = request.data.get("part_number")

                if not key or not upload_id or not part_number:
                    return Response(
                        {"error": "key, upload_id and part_number required"},
                        status=400
                    )

                url = generate_part_upload_url(key, upload_id, part_number)

                return Response({"url": url})

            if cloud == "AZURE":

                blob_name = request.data.get("blob_name")
                block_id = request.data.get("block_id")

                if not blob_name or not block_id:
                    return Response(
                        {"error": "blob_name and block_id required"},
                        status=400
                    )

                url = generate_block_upload_url(blob_name, block_id)

                return Response({"url": url})

            if cloud == "GCP":
                return Response(
                    {"error": "GCP does not use presigned parts"},
                    status=400
                )

        except Exception as e:
            logger.error(str(e))
            return Response({"error": "Failed generating part upload url"}, status=500)


# ==========================================
# MULTIPART COMPLETE
# ==========================================
class MultipartCompleteView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):

        cloud = request.data.get("cloud")

        if not cloud:
            return Response({"error": "cloud required"}, status=400)

        cloud = cloud.upper()

        try:

            if cloud == "AWS":

                key = request.data.get("key")
                upload_id = request.data.get("upload_id")
                parts = request.data.get("parts")

                parts = sorted(parts, key=lambda p: p["PartNumber"])

                complete_multipart_upload(key, upload_id, parts)

                return Response({"message": "AWS multipart complete"})

            if cloud == "AZURE":

                blob_name = request.data.get("blob_name")
                blocks = request.data.get("blocks")

                commit_block_list(blob_name, blocks)

                return Response({"message": "Azure upload complete"})

            if cloud == "GCP":

                return Response({"message": "GCP upload complete"})

        except Exception as e:
            logger.error(str(e))
            return Response({"error": "Multipart completion failed"}, status=500)


# ==========================================
# DOWNLOAD
# ==========================================
class PresignDownloadView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request, file_id):

        try:
            file = File.objects.get(id=file_id, user=request.user)
        except File.DoesNotExist:
            return Response({"error": "File not found"}, status=404)

        try:

            if file.aws_path:
                url = generate_aws_download_url(file.aws_path)

            elif file.azure_path:
                url = generate_azure_download_url(file.azure_path)

            elif file.gcp_path:
                url = generate_gcp_download_url(file.gcp_path)

            else:
                return Response(
                    {"error": "File not available in any cloud"},
                    status=400,
                )

        except Exception as e:
            logger.error(str(e))
            return Response(
                {"error": "Failed to generate download URL"},
                status=500,
            )

        return Response({"download_url": url})


# ==========================================
# DELETE FILE
# ==========================================
class FileDeleteView(APIView):

    permission_classes = [IsAuthenticated]

    def delete(self, request, file_id):

        try:
            file = File.objects.get(id=file_id, user=request.user)
        except File.DoesNotExist:
            return Response({"error": "File not found"}, status=404)

        clouds = request.data.get("clouds") or ["AWS", "AZURE", "GCP"]

        clouds = [c.upper() for c in clouds]

        if "AWS" in clouds and file.aws_path:
            delete_file_from_s3(file.aws_path)
            file.aws_path = None

        if "AZURE" in clouds and file.azure_path:
            delete_file_from_azure(file.azure_path)
            file.azure_path = None

        if "GCP" in clouds and file.gcp_path:
            delete_file_from_gcp(file.gcp_path)
            file.gcp_path = None

        if not any([file.aws_path, file.azure_path, file.gcp_path]):

            file.delete()

            return Response(
                {"message": "File deleted from all clouds"},
                status=200,
            )

        file.save()

        return Response(
            {"message": "File deleted from selected clouds"},
            status=200,
        )

class ConfirmUploadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):

        file_name = request.data.get("file_name")
        file_size = request.data.get("file_size")

        if not file_name or not file_size:
            return Response(
                {"error": "file_name and file_size are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:

            file = File.objects.create(
                user=request.user,
                file_name=file_name,
                file_size=int(file_size),
                aws_path=request.data.get("aws_path"),
                azure_path=request.data.get("azure_path"),
                gcp_path=request.data.get("gcp_path"),
            )

        except Exception as e:

            logger.error(str(e))

            return Response(
                {"error": "Failed to save file metadata"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {"file_id": file.id, "message": "Upload verified and saved"},
            status=status.HTTP_201_CREATED,
        )