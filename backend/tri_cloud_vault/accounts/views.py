import uuid
from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import send_mail
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from .models import EmailVerification
from .serializers import RegisterSerializer
from django.shortcuts import redirect
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()

        # Generate verification token
        token = uuid.uuid4().hex

        EmailVerification.objects.create(
            user=user,
            token=token
        )

        verification_link = f"http://127.0.0.1:8000/api/auth/verify-email?token={token}"

        send_mail(
            subject="Verify your TriCloud Vault account",
            message=f"Click the link to verify your account:\n{verification_link}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )

        return Response(
            {
                "message": "Registration successful. Please verify your email."
            },
            status=status.HTTP_201_CREATED
        )
    
class VerifyEmailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        token = request.query_params.get("token")

        if not token:
            return Response(
                {"error": "Token is missing"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            verification = EmailVerification.objects.get(token=token)
        except EmailVerification.DoesNotExist:
            return Response(
                {"error": "Invalid or expired token"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if verification.is_verified:
            return Response(
                {"message": "Email already verified"},
                status=status.HTTP_200_OK
            )

        # Mark verified
        verification.is_verified = True
        verification.save()

        # Activate user
        user = verification.user
        user.is_active = True
        user.save()

        return Response(
            {"message": "Email verified successfully. You can now log in."},
            status=status.HTTP_200_OK
        )

class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        if not username or not password:
            return Response(
                {"error": "Username and password are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = authenticate(username=username, password=password)

        if user is None:
            return Response(
                {"error": "Invalid credentials"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if not user.is_active:
            return Response(
                {"error": "Email not verified"},
                status=status.HTTP_403_FORBIDDEN
            )

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_200_OK
        )

