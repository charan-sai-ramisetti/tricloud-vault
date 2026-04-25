from .admin_dashboard import admin_site
from .health import HealthCheckView
from .metrics import MetricsView
from django.urls import path, include

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="health-check"),
    path("api/metrics/", MetricsView.as_view(), name="metrics"),
    path("admin/", admin_site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/files/", include("files.urls")),
    path("api/payments/", include("payments.urls")),
    path("api/storage/", include("dashboard.urls")),
]