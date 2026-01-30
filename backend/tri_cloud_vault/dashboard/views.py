from django.db.models import Sum
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from files.models import File
from payments.models import Subscription

from django.db.models import Sum
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from files.models import File
from payments.models import Subscription


class StorageSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        subscription = Subscription.objects.get(user=user)
        limit_mb = subscription.cloud_limit_mb

        aws_used = (
            File.objects.filter(user=user, aws_path__isnull=False)
            .aggregate(total=Sum("file_size"))["total"] or 0
        )

        azure_used = (
            File.objects.filter(user=user, azure_path__isnull=False)
            .aggregate(total=Sum("file_size"))["total"] or 0
        )

        gcp_used = (
            File.objects.filter(user=user, gcp_path__isnull=False)
            .aggregate(total=Sum("file_size"))["total"] or 0
        )

        return Response({
            "aws": {
                "used_mb": round(aws_used / (1024 * 1024), 2),
                "limit_mb": limit_mb
            },
            "azure": {
                "used_mb": round(azure_used / (1024 * 1024), 2),
                "limit_mb": limit_mb
            },
            "gcp": {
                "used_mb": round(gcp_used / (1024 * 1024), 2),
                "limit_mb": limit_mb
            }
        })


class RecentFilesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        files = (
            File.objects
            .filter(user=user)
            .order_by("-created_at")[:5]
        )

        data = []
        for f in files:
            clouds = []
            if f.aws_path:
                clouds.append("AWS")
            if f.azure_path:
                clouds.append("Azure")
            if f.gcp_path:
                clouds.append("GCP")

            data.append({
                "id": f.id,
                "file_name": f.file_name,
                "size_mb": round((f.file_size or 0) / (1024 * 1024), 2),
                "uploaded_at": f.created_at,
                "clouds": clouds
            })

        return Response(data)


class FolderSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        files = File.objects.filter(user=user)

        folders = {
            "Documents": ["pdf", "doc", "docx", "txt"],
            "Images": ["jpg", "jpeg", "png", "gif"],
            "Videos": ["mp4", "mkv", "avi"],
        }

        result = {
            "Documents": {"count": 0, "size": 0},
            "Images": {"count": 0, "size": 0},
            "Videos": {"count": 0, "size": 0},
            "Others": {"count": 0, "size": 0},
        }

        for f in files:
            ext = f.file_name.split(".")[-1].lower()
            matched = False

            for folder, exts in folders.items():
                if ext in exts:
                    result[folder]["count"] += 1
                    result[folder]["size"] += f.file_size or 0
                    matched = True
                    break

            if not matched:
                result["Others"]["count"] += 1
                result["Others"]["size"] += f.file_size or 0

        response = []
        for name, data in result.items():
            response.append({
                "name": name,
                "count": data["count"],
                "size_mb": round(data["size"] / (1024 * 1024), 2)
            })

        return Response(response)
