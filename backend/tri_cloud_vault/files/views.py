from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.db.models import Sum

from payments.models import Subscription
from .models import File
from .serializers import FileSerializer

# ========= AWS =========
from clouds.aws import (
    generate_aws_upload_url,
    generate_aws_download_url,
    delete_file_from_s3,
)

# ========= AZURE =========
from clouds.azure import (
    generate_azure_upload_url,
    generate_azure_download_url,
    delete_file_from_azure,
)

# ========= GCP =========
from clouds.gcp import (
    generate_gcp_upload_url,
    generate_gcp_download_url,
    delete_file_from_gcp,
)

ALLOWED_CLOUDS = {"AWS", "AZURE", "GCP"}


class FileListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        files = File.objects.filter(user=request.user).order_by("-created_at")
        serializer = FileSerializer(files, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PresignUploadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        file_name = request.data.get("file_name")
        file_size = request.data.get("file_size")
        clouds = request.data.get("clouds", [])

        if not file_name or not file_size or not clouds:
            return Response(
                {"error": "file_name, file_size and clouds are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        MAX_FILE_SIZE_MB = 100
        if file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
            return Response(
                {"error": "File size exceeds 100 MB limit"},
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

        for cloud in clouds:
            if cloud == "AWS":
                used = File.objects.filter(
                    user=request.user, aws_path__isnull=False
                ).aggregate(total=Sum("file_size"))["total"] or 0
            elif cloud == "AZURE":
                used = File.objects.filter(
                    user=request.user, azure_path__isnull=False
                ).aggregate(total=Sum("file_size"))["total"] or 0
            else:
                used = File.objects.filter(
                    user=request.user, gcp_path__isnull=False
                ).aggregate(total=Sum("file_size"))["total"] or 0

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

        if "AWS" in clouds:
            try:
                key, url = generate_aws_upload_url(
                    request.user.id, file_name
                )
                upload_urls["AWS"] = url
                paths["aws_path"] = key
            except Exception as e:
                upload_urls["AWS"] = None

        if "AZURE" in clouds:
            try:
                key, url = generate_azure_upload_url(
                    request.user.id, file_name
                )
                upload_urls["AZURE"] = url
                paths["azure_path"] = key
            except Exception:
                upload_urls["AZURE"] = None

        if "GCP" in clouds:
            try:
                key, url = generate_gcp_upload_url(
                    request.user.id, file_name
                )
                upload_urls["GCP"] = url
                paths["gcp_path"] = key
            except Exception:
                upload_urls["GCP"] = None

        return Response(
            {"upload_urls": upload_urls, "paths": paths},
            status=status.HTTP_200_OK,
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

        verified_size = None

        try:
            file = File.objects.create(
                user=request.user,
                file_name=file_name,
                file_size=file_size,
                aws_path=request.data.get("aws_path"),
                azure_path=request.data.get("azure_path"),
                gcp_path=request.data.get("gcp_path"),
            )
        except Exception:
            return Response(
                {"error": "Failed to save file metadata"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {"file_id": file.id, "message": "Upload verified and saved"},
            status=status.HTTP_201_CREATED,
        )


class PresignDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, file_id):
        try:
            file = File.objects.get(id=file_id, user=request.user)
        except File.DoesNotExist:
            return Response(
                {"error": "File not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

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
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except Exception:
            return Response(
                {"error": "Failed to generate download URL"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {"download_url": url},
            status=status.HTTP_200_OK,
        )


class FileDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, file_id):
        try:
            file = File.objects.get(id=file_id, user=request.user)
        except File.DoesNotExist:
            return Response(
                {"error": "File not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        clouds = request.data.get("clouds") or ["AWS", "AZURE", "GCP"]
        clouds = [c.upper() for c in clouds]

        if "AWS" in clouds and file.aws_path:
            try:
                delete_file_from_s3(file.aws_path)
                file.aws_path = None
            except Exception:
                pass

        if "AZURE" in clouds and file.azure_path:
            try:
                delete_file_from_azure(file.azure_path)
                file.azure_path = None
            except Exception:
                pass

        if "GCP" in clouds and file.gcp_path:
            try:
                delete_file_from_gcp(file.gcp_path)
                file.gcp_path = None
            except Exception:
                pass

        if not any([file.aws_path, file.azure_path, file.gcp_path]):
            file.delete()
            return Response(
                {"message": "File deleted from all clouds"},
                status=status.HTTP_200_OK,
            )

        file.save()
        return Response(
            {"message": "File deleted from selected clouds"},
            status=status.HTTP_200_OK,
        )
