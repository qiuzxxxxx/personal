from django.urls import path

from . import views

urlpatterns = [
    path("messages/", views.messages, name="chat-messages"),
    path("files/", views.upload_file, name="chat-file-upload"),
    path(
        "files/<uuid:message_id>/download/",
        views.download_file,
        name="chat-file-download",
    ),
]