# payments/models.py
from django.db import models
from django.contrib.auth.models import User

class Subscription(models.Model):
    PLAN_CHOICES = (
        ("FREE", "Free"),
        ("PRO", "Pro"),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE)

    plan = models.CharField(
        max_length=10,
        choices=PLAN_CHOICES,
        default="FREE"
    )

    cloud_limit_mb = models.IntegerField(default=1024)  # 1 GB
    max_file_size_mb = models.IntegerField(default=100)

    upgraded_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.plan}"

# payments/models.py
class Payment(models.Model):
    STATUS_CHOICES = (
        ("CREATED", "Created"),
        ("SUCCESS", "Success"),
        ("FAILED", "Failed"),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE)

    razorpay_order_id = models.CharField(max_length=255, unique=True)
    razorpay_payment_id = models.CharField(
        max_length=255, null=True, blank=True
    )

    amount = models.IntegerField()  # 500 (INR)
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="CREATED"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.status}"
