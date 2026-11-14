from django.contrib import admin
from django.urls import include, path
from django.http import JsonResponse


def healthcheck(_request):
    return JsonResponse({"status": "ok", "service": "zixxx"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", healthcheck, name="health"),
    path("api/auth/", include("accounts.urls")),
    path("api/agent/", include("agent.urls")),
    path("api/chat/", include("chat.urls")),
    path("api/transfer/", include("transfer.urls")),
]