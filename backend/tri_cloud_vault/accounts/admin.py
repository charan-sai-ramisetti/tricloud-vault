from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    model = User

    list_display = (
        "email",
        "username",
        "is_email_verified",
        "is_staff",
        "is_active",
    )

    list_filter = (
        "is_email_verified",
        "is_staff",
        "is_active",
    )

    search_fields = ("email", "username")
    ordering = ("email",)

    fieldsets = UserAdmin.fieldsets + (
        ("Email Verification", {"fields": ("is_email_verified",)}),
    )
