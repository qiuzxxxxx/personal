from django.contrib import admin
from django.urls import include, path

from .health import health, live


urlpatterns = [
    path("admin/", admin.site.urls),
    # Liveness only reports the process; readiness also checks the database
    # and Redis. Neither endpoint exposes any user data.
    path("api/health/live/", live, name="health-live"),
    path("api/health/ready/", health, name="health-ready"),
    path("api/auth/", include("accounts.urls")),
    path("api/agent/", include("agent.urls")),
    path("api/chat/", include("chat.urls")),
    path("api/transfer/", include("transfer.urls")),
    path("api/", include("workspace.urls")),
    path("api/", include("knowledge.urls")),
    path("api/upload/", include("workspace.upload_urls")),
]
