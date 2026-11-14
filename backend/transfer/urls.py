from django.urls import path

from . import views

urlpatterns = [
    path("files/", views.files, name="transfer-files"),
    path("files/<uuid:file_id>/", views.file_detail, name="transfer-file-detail"),
    path(
        "files/<uuid:file_id>/download/",
        views.download,
        name="transfer-file-download",
    ),
]