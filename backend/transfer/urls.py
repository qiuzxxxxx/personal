from django.urls import path

from . import views

urlpatterns = [
    path("announcement/", views.announcement, name="transfer-announcement"),
    path(
        "login-announcement/",
        views.login_announcement,
        name="transfer-login-announcement",
    ),
    path(
        "announcement-history/",
        views.announcement_history,
        name="transfer-announcement-history",
    ),
    path("files/", views.files, name="transfer-files"),
    path("files/<uuid:file_id>/", views.file_detail, name="transfer-file-detail"),
    path(
        "files/<uuid:file_id>/download/",
        views.download,
        name="transfer-file-download",
    ),
]
