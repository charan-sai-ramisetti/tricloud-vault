from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import File
from .serializers import FileSerializer,FileUploadSerializer
from rest_framework import status
from clouds.aws import upload_file_to_s3
from clouds.aws import download_file_from_s3
from django.http import StreamingHttpResponse
from clouds.aws import delete_file_from_s3
from clouds.azure import upload_file_to_azure
from clouds.azure import download_file_from_azure
from clouds.azure import delete_file_from_azure
from clouds.gcp import upload_file_to_gcp
from clouds.gcp import download_file_from_gcp
from clouds.gcp import delete_file_from_gcp




class FileListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        files = File.objects.filter(user=request.user).order_by("-created_at")
        serializer = FileSerializer(files, many=True)
        return Response(serializer.data)

class FileUploadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = FileUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        file_obj = serializer.validated_data["file"]
        clouds = serializer.validated_data["clouds"]
        aws_path = None
        azure_path = None
        gcp_path = None

        if "AWS" in clouds:
            aws_path = upload_file_to_s3(file_obj, request.user.id)

        if "AZURE" in clouds:
            azure_path = upload_file_to_azure(file_obj, request.user.id)
        
        if "GCP" in clouds:
            gcp_path = upload_file_to_gcp(file_obj, request.user.id)

        file_record = File.objects.create(
            user=request.user,
            file_name=file_obj.name,
            file_size=file_obj.size,
            aws_path=aws_path,
            azure_path=azure_path,
            gcp_path=gcp_path,
        )


        return Response(
            {
                "message": "File uploaded successfully",
                "file_id": file_record.id,
                "uploaded_to": clouds,
                "aws_path": aws_path,
            },
            status=status.HTTP_201_CREATED,
        )
    

from django.http import StreamingHttpResponse
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import File
from clouds.aws import download_file_from_s3
from clouds.azure import download_file_from_azure


class FileDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, file_id):
        try:
            file_record = File.objects.get(id=file_id, user=request.user)
        except File.DoesNotExist:
            return Response(
                {"error": "File not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Cloud priority: AWS → Azure → GCP
        if file_record.aws_path:
            file_stream = download_file_from_s3(file_record.aws_path)
        elif file_record.azure_path:
            file_stream = download_file_from_azure(file_record.azure_path)
        elif file_record.gcp_path:
            file_stream = download_file_from_gcp(file_record.gcp_path)
        else:
            return Response(
                {"error": "File not available in any cloud"},
                status=status.HTTP_400_BAD_REQUEST
            )

        response = StreamingHttpResponse(
            file_stream,
            content_type="application/octet-stream"
        )
        response["Content-Disposition"] = (
            f'attachment; filename="{file_record.file_name}"'
        )
        return response
    

ALLOWED_CLOUDS = {"AWS", "AZURE", "GCP"}


class FileDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, file_id):
        clouds = request.data.get("clouds")

        try:
            file_record = File.objects.get(id=file_id, user=request.user)
        except File.DoesNotExist:
            return Response(
                {"error": "File not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # If no clouds provided → delete from ALL
        if not clouds:
            clouds = ["AWS", "AZURE", "GCP"]
        else:
            clouds = [c.upper() for c in clouds]

        # AWS
        if "AWS" in clouds and file_record.aws_path:
            delete_file_from_s3(file_record.aws_path)
            file_record.aws_path = None

        # AZURE
        if "AZURE" in clouds and file_record.azure_path:
            delete_file_from_azure(file_record.azure_path)
            file_record.azure_path = None

        # GCP (future)
        if "GCP" in clouds and file_record.gcp_path:
            delete_file_from_gcp(file_record.gcp_path)
            file_record.gcp_path = None

        # If nothing left → delete DB record
        if not any([
            file_record.aws_path,
            file_record.azure_path,
            file_record.gcp_path
        ]):
            file_record.delete()
            return Response(
                {"message": "File deleted from all clouds"},
                status=status.HTTP_200_OK
            )

        file_record.save()
        return Response(
            {
                "message": "File deleted from selected clouds",
                "remaining_clouds": [
                    c for c in ["AWS", "AZURE", "GCP"]
                    if getattr(file_record, f"{c.lower()}_path", None)
                ]
            },
            status=status.HTTP_200_OK
        )
