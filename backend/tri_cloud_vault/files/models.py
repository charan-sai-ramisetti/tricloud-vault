from django.contrib.auth.models import User
from django.db import models


class File(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="files")

    file_name = models.CharField(max_length=255)
    file_size = models.BigIntegerField(help_text="Size in bytes")

    # cloud locations (nullable → user may not choose all)
    aws_path = models.CharField(max_length=512, null=True, blank=True)
    azure_path = models.CharField(max_length=512, null=True, blank=True)
    gcp_path = models.CharField(max_length=512, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.file_name} ({self.user.username})"
