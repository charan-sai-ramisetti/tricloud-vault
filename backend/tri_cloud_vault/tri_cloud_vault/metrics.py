import psutil
import time
from django.http import JsonResponse
from django.views import View

psutil.cpu_percent(interval=None)


class MetricsView(View):
    def get(self, request):
        cpu_pct = psutil.cpu_percent(interval=None)

        mem = psutil.virtual_memory()
        ram_pct = round(mem.percent, 1)
        ram_used_mb = round(mem.used / (1024 * 1024), 1)
        ram_total_mb = round(mem.total / (1024 * 1024), 1)

        return JsonResponse({
            "timestamp": time.time(),
            "cpu_pct": round(cpu_pct, 1),
            "ram_pct": ram_pct,
            "ram_used_mb": ram_used_mb,
            "ram_total_mb": ram_total_mb,
        })