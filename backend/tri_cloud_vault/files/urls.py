from django.urls import path
from .views import (
    FileListView,
    PresignUploadView,
    PresignDownloadView,
    FileDeleteView,
    ConfirmUploadView,
)

urlpatterns = [
    path("", FileListView.as_view()),
    path("presign/upload/", PresignUploadView.as_view()),
    path("confirm-upload/", ConfirmUploadView.as_view()),
    path("<int:file_id>/presign/download/", PresignDownloadView.as_view()),
    path("<int:file_id>/", FileDeleteView.as_view()),
]
