from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from .models import File
from .serializers import FileSerializer

# ========= AWS PRESIGN =========
from clouds.aws import (
    generate_aws_upload_url,
    generate_aws_download_url,
    delete_file_from_s3,
)

# ========= AZURE PRESIGN =========
from clouds.azure import (
    generate_azure_upload_url,
    generate_azure_download_url,
    delete_file_from_azure,
)

# ========= GCP PRESIGN =========
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
        print(request.data)
        file_name = request.data.get("file_name")
        clouds = request.data.get("clouds", [])

        if not file_name or not clouds:
            return Response(
                {"error": "file_name and clouds are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        clouds = [c.upper() for c in clouds]
        invalid = set(clouds) - ALLOWED_CLOUDS
        if invalid:
            return Response(
                {"error": f"Invalid clouds: {', '.join(invalid)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        upload_urls = {}
        paths = {}

        if "AWS" in clouds:
            key, url = generate_aws_upload_url(request.user.id, file_name)
            upload_urls["AWS"] = url
            paths["aws_path"] = key

        if "AZURE" in clouds:
            key, url = generate_azure_upload_url(request.user.id, file_name)
            upload_urls["AZURE"] = url
            paths["azure_path"] = key

        if "GCP" in clouds:
            key, url = generate_gcp_upload_url(request.user.id, file_name)
            upload_urls["GCP"] = url
            paths["gcp_path"] = key

        return Response(
            {
                "upload_urls": upload_urls,
                "paths": paths,
            },
            status=status.HTTP_200_OK,
        )

class ConfirmUploadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        file_name = request.data.get("file_name")
        file_size = request.data.get("file_size")

        aws_path = request.data.get("aws_path")
        azure_path = request.data.get("azure_path")
        gcp_path = request.data.get("gcp_path")

        if not file_name or not file_size:
            return Response(
                {"error": "file_name and file_size are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        verified_size = None

        # ---------- AWS VERIFICATION ----------
        if aws_path:
            try:
                from clouds.aws import s3, AWS_BUCKET
                meta = s3.head_object(Bucket=AWS_BUCKET, Key=aws_path)
                verified_size = meta["ContentLength"]
                print(verified_size)
            except Exception:
                return Response(
                    {"error": "AWS file not found"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # ---------- AZURE VERIFICATION ----------
        if azure_path:
            try:
                from clouds.azure import service, AZURE_CONTAINER
                blob = service.get_blob_client(AZURE_CONTAINER, azure_path)
                props = blob.get_blob_properties()
                verified_size = props.size
            except Exception:
                return Response(
                    {"error": "Azure file not found"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # ---------- GCP VERIFICATION ----------
        if gcp_path:
            try:
                from clouds.gcp import bucket
                blob = bucket.blob(gcp_path)
                blob.reload()
                verified_size = blob.size
            except Exception:
                return Response(
                    {"error": "GCP file not found"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if verified_size != file_size:
            return Response(
                {"error": "File size mismatch"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        file = File.objects.create(
            user=request.user,
            file_name=file_name,
            file_size=verified_size,
            aws_path=aws_path,
            azure_path=azure_path,
            gcp_path=gcp_path,
        )

        return Response(
            {
                "file_id": file.id,
                "message": "Upload verified and saved"
            },
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

        return Response(
            {"download_url": url},
            status=status.HTTP_200_OK,
        )


class FileDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, file_id):
        clouds = request.data.get("clouds")

        try:
            file = File.objects.get(id=file_id, user=request.user)
        except File.DoesNotExist:
            return Response(
                {"error": "File not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # If no clouds provided → delete from ALL
        if not clouds:
            clouds = ["AWS", "AZURE", "GCP"]
        else:
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
                status=status.HTTP_200_OK,
            )

        file.save()
        return Response(
            {
                "message": "File deleted from selected clouds",
                "remaining_clouds": [
                    c for c in ["AWS", "AZURE", "GCP"]
                    if getattr(file, f"{c.lower()}_path", None)
                ],
            },
            status=status.HTTP_200_OK,
        )


