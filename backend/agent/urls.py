from django.urls import path

from . import views

urlpatterns = [
    path("config/", views.api_config_view, name="agent-config"),
    path("suggestions/", views.suggestions, name="agent-suggestions"),
    path("config/test/", views.test_connection, name="agent-config-test"),
    path("conversations/", views.conversations, name="agent-conversations"),
    path(
        "conversations/<uuid:conversation_id>/",
        views.conversation_detail,
        name="agent-conversation-detail",
    ),
    path(
        "conversations/<uuid:conversation_id>/messages/",
        views.conversation_messages,
        name="agent-conversation-messages",
    ),
    path("attachments/", views.upload_attachment, name="agent-attachment-upload"),
    path("chat/", views.chat, name="agent-chat"),
]
