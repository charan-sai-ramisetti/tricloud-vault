import uuid

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.core.mail import send_mail
from django.shortcuts import redirect

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import RegisterSerializer
from django.utils import timezone
from datetime import timedelta

User = get_user_model()


# -------------------------
# REGISTER
# -------------------------
class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        
        serializer = RegisterSerializer(data=request.data)
        print(request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "error": "Validation failed",
                    "details": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = serializer.save()
        except Exception:
            return Response(
                {"error": "Unable to create user"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        verification_link = (
            f"http://127.0.0.1:8000/api/auth/verify-email?"
            f"token={user.email_verification_token}"
        )

        send_mail(
            subject="Verify your TriCloud Vault account",
            message=(
                "Welcome to TriCloud Vault!\n\n"
                "Please verify your email by clicking the link below:\n\n"
                f"{verification_link}"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )

        return Response(
            {
                "message": "Registration successful. Please verify your email."
            },
            status=status.HTTP_201_CREATED,
        )


# -------------------------
# VERIFY EMAIL
# -------------------------
class VerifyEmailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        token = request.query_params.get("token")

        if not token:
            return redirect("http://127.0.0.1:5500/auth/verify-failed.html")

        try:
            user = User.objects.get(email_verification_token=token)
        except User.DoesNotExist:
            return redirect("http://127.0.0.1:5500/auth/verify-failed.html")

        if user.is_email_verified:
            return redirect("http://127.0.0.1:5500/auth/verify-success.html")

        user.is_email_verified = True
        user.is_active = True
        user.email_verification_token = None
        user.save(update_fields=["is_email_verified", "is_active", "email_verification_token"])

        return redirect("http://127.0.0.1:5500/auth/verify-success.html")


# -------------------------
# LOGIN
# -------------------------
class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")
        print(request.data)
        if not email or not password:
            return Response(
                {"error": "Email and password are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(request, username=email, password=password)

        if not user:
            return Response(
                {"error": "Invalid credentials"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_email_verified:
            return Response(
                {"error": "Email not verified"},
                status=status.HTTP_403_FORBIDDEN,
            )

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_200_OK,
        )


# -------------------------
# RESEND VERIFICATION
# -------------------------
class ResendVerificationEmailView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")

        if not email:
            return Response(
                {"error": "Email is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"error": "No account found with this email"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if user.is_email_verified:
            return Response(
                {"message": "Email already verified"},
                status=status.HTTP_200_OK,
            )

        user.email_verification_token = uuid.uuid4()
        user.save(update_fields=["email_verification_token"])

        verification_link = (
            f"http://127.0.0.1:8000/api/auth/verify-email?"
            f"token={user.email_verification_token}"
        )

        send_mail(
            subject="Resend: Verify your TriCloud Vault account",
            message=f"Verify your email:\n\n{verification_link}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )

        return Response(
            {"message": "Verification email resent"},
            status=status.HTTP_200_OK,
        )

from django.utils import timezone
from datetime import timedelta

class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")

        if not email:
            return Response(
                {"error": "Email is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # IMPORTANT: do NOT reveal if email exists
            return Response(
                {"message": "If the email exists, a reset link was sent"},
                status=status.HTTP_200_OK
            )

        user.reset_password_token = uuid.uuid4()
        user.reset_password_expiry = timezone.now() + timedelta(minutes=30)
        user.save(update_fields=["reset_password_token", "reset_password_expiry"])

        reset_link = (
            f"http://127.0.0.1:5500/auth/reset-password.html?"
            f"token={user.reset_password_token}"
        )

        send_mail(
            subject="Reset your TriCloud Vault password",
            message=f"Reset your password:\n\n{reset_link}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False
        )

        return Response(
            {"message": "If the email exists, a reset link was sent"},
            status=status.HTTP_200_OK
        )

class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get("token")
        password = request.data.get("password")

        if not token or not password:
            return Response(
                {"error": "Token and password required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(
                reset_password_token=token,
                reset_password_expiry__gt=timezone.now()
            )
        except User.DoesNotExist:
            return Response(
                {"error": "Invalid or expired token"},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(password)
        user.reset_password_token = None
        user.reset_password_expiry = None
        user.save(update_fields=[
            "password",
            "reset_password_token",
            "reset_password_expiry"
        ])

        return Response(
            {"message": "Password reset successful"},
            status=status.HTTP_200_OK
        )
