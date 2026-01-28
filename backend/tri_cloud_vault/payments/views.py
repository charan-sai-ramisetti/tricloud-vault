import os
import razorpay
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from .models import Payment, Subscription
from .serializers import PaymentVerifySerializer

razorpay_client = razorpay.Client(
    auth=(
        os.getenv("RAZORPAY_KEY_ID"),
        os.getenv("RAZORPAY_KEY_SECRET")
    )
)

class SubscriptionStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        subscription, _ = Subscription.objects.get_or_create(
            user=request.user,
            defaults={
                "plan": "FREE",
                "cloud_limit_mb": 1024,
                "max_file_size_mb": 100
            }
        )

        return Response({
            "plan": subscription.plan,
            "cloud_limit_mb": subscription.cloud_limit_mb,
            "max_file_size_mb": subscription.max_file_size_mb,
            "is_upgraded": subscription.plan == "PRO"
        })

class CreateOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        amount = 500 * 100  # ₹500 → paise

        order = razorpay_client.order.create({
            "amount": amount,
            "currency": "INR",
            "payment_capture": 1
        })

        Payment.objects.create(
            user=request.user,
            razorpay_order_id=order["id"],
            amount=500,
            status="CREATED"
        )

        return Response({
            "order_id": order["id"],
            "razorpay_key": os.getenv("RAZORPAY_KEY_ID"),
            "amount": amount,
            "currency": "INR"
        })

class VerifyPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PaymentVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data


        razorpay_order_id = data.get("razorpay_order_id")
        razorpay_payment_id = data.get("razorpay_payment_id")
        razorpay_signature = data.get("razorpay_signature")

        try:
            razorpay_client.utility.verify_payment_signature({
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_signature": razorpay_signature
            })
        except razorpay.errors.SignatureVerificationError:
            return Response(
                {"error": "Invalid payment signature"},
                status=status.HTTP_400_BAD_REQUEST
            )

        payment = Payment.objects.get(
            razorpay_order_id=razorpay_order_id,
            user=request.user
        )

        payment.razorpay_payment_id = razorpay_payment_id
        payment.status = "SUCCESS"
        payment.save()

        subscription, _ = Subscription.objects.get_or_create(user=request.user)
        subscription.plan = "PRO"
        subscription.cloud_limit_mb = 50 * 1024  # 50 GB
        subscription.upgraded_at = timezone.now()
        subscription.save()

        return Response({
            "message": "Payment verified. Subscription upgraded.",
            "plan": "PRO"
        })

@method_decorator(csrf_exempt, name="dispatch")
class RazorpayWebhookView(APIView):
    authentication_classes = []   # ❌ no JWT
    permission_classes = []       # ❌ no auth

    def post(self, request):
        webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET")
        payload = request.body.decode("utf-8")
        received_signature = request.headers.get("X-Razorpay-Signature")

        try:
            razorpay_client.utility.verify_webhook_signature(
                payload,
                received_signature,
                webhook_secret
            )
        except razorpay.errors.SignatureVerificationError:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        event = request.data.get("event")

        if event == "payment.captured":
            entity = request.data["payload"]["payment"]["entity"]
            order_id = entity["order_id"]
            payment_id = entity["id"]

            try:
                payment = Payment.objects.get(
                    razorpay_order_id=order_id
                )
                payment.razorpay_payment_id = payment_id
                payment.status = "SUCCESS"
                payment.save()

                subscription, _ = Subscription.objects.get_or_create(
                    user=payment.user
                )
                subscription.plan = "PRO"
                subscription.cloud_limit_mb = 50 * 1024
                subscription.upgraded_at = timezone.now()
                subscription.save()

            except Payment.DoesNotExist:
                pass  # safe ignore

        return Response(status=status.HTTP_200_OK)

